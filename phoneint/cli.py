# file: phoneint/cli.py
"""
phoneint CLI.

Commands:
  - lookup: parse/enrich a phone number and run optional reputation adapters
  - report: export an existing JSON report into CSV/PDF
  - serve-gui: launch the (optional) PySide6 GUI
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import click

from phoneint import __version__
from phoneint.cache import CachedReputationAdapter, SQLiteTTLCache
from phoneint.config import PhoneintSettings, load_settings
from phoneint.core.enrich import enrich_number
from phoneint.core.parser import InvalidPhoneNumberError, MissingCountryError, parse_and_normalize
from phoneint.io.report import LEGAL_DISCLAIMER, export_csv, export_json, generate_pdf, utc_now_iso
from phoneint.logging_config import configure_logging
from phoneint.net.http import PerHostRateLimiter, build_async_client
from phoneint.reputation.adapter import ReputationAdapter, SearchResult
from phoneint.reputation.duckduckgo import DuckDuckGoInstantAnswerAdapter
from phoneint.reputation.google import GoogleCustomSearchAdapter
from phoneint.reputation.public import PublicScamListAdapter
from phoneint.reputation.score import infer_domain_signals, score_risk

logger = logging.getLogger(__name__)


def _parse_adapters_csv(value: str) -> list[str]:
    names = [v.strip().lower() for v in value.split(",") if v.strip()]
    # Deduplicate while preserving order.
    out: list[str] = []
    for n in names:
        if n not in out:
            out.append(n)
    return out


async def _run_adapters(
    adapters: list[ReputationAdapter], e164: str
) -> tuple[list[SearchResult], dict[str, str]]:
    tasks: list[asyncio.Task[list[SearchResult]]] = []
    names: list[str] = []
    for ad in adapters:
        names.append(ad.name)
        tasks.append(asyncio.create_task(ad.check(e164, limit=5)))

    all_results: list[SearchResult] = []
    errors: dict[str, str] = {}

    for name, task in zip(names, tasks):
        try:
            results = await task
            all_results.extend(results)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"

    return all_results, errors


async def lookup_async(
    number: str,
    *,
    settings: PhoneintSettings,
    adapters: list[str],
    region: str | None,
    no_cache: bool,
) -> dict[str, Any]:
    parsed, normalized = parse_and_normalize(
        number, default_region=region or settings.default_region
    )
    enrichment = enrich_number(parsed)

    http_config = settings.http_config()
    rate_limiter = PerHostRateLimiter(rate_per_second=http_config.rate_limit_per_host_per_second)

    cache: SQLiteTTLCache | None = None
    if settings.cache_enabled and not no_cache:
        cache = SQLiteTTLCache(settings.cache_path)

    async with build_async_client(http_config) as client:
        rep_adapters: list[ReputationAdapter] = []
        for name in adapters:
            if name in ("duckduckgo", "ddg"):
                rep_adapters.append(
                    DuckDuckGoInstantAnswerAdapter(
                        client=client, http_config=http_config, rate_limiter=rate_limiter
                    )
                )
            elif name in ("google", "gcs"):
                try:
                    rep_adapters.append(
                        GoogleCustomSearchAdapter(
                            client=client,
                            http_config=http_config,
                            api_key=settings.gcs_api_key,
                            cx=settings.gcs_cx,
                            rate_limiter=rate_limiter,
                        )
                    )
                except Exception as exc:
                    logger.warning("Google adapter disabled: %s", exc)
            elif name in ("public", "scam_db", "scamdb"):
                rep_adapters.append(PublicScamListAdapter(scam_list_path=settings.scam_list_path))
            else:
                logger.warning("Unknown adapter: %s", name)

        if cache is not None:
            rep_adapters = [
                CachedReputationAdapter(ad, cache=cache, ttl_seconds=settings.cache_ttl_seconds)
                for ad in rep_adapters
            ]

        evidence, adapter_errors = await _run_adapters(rep_adapters, normalized.e164)

    found_in_scam_db = any(r.source == "public_scam_db" for r in evidence)
    domain_signals = infer_domain_signals(evidence)
    voip = enrichment.number_type == "voip"

    score = score_risk(
        found_in_scam_db=found_in_scam_db,
        voip=voip,
        found_in_classifieds=domain_signals["found_in_classifieds"],
        business_listing=domain_signals["business_listing"],
        age_of_first_mention_days=None,
        weights=settings.score_weights,
    )

    exec_summary = (
        f"Risk score {score.score}/100. "
        f"Matched scam dataset: {'yes' if found_in_scam_db else 'no'}. "
        f"Evidence items: {len(evidence)}."
    )

    report: dict[str, Any] = {
        "metadata": {
            "tool": "phoneint",
            "version": __version__,
            "generated_at": utc_now_iso(),
        },
        "query": {"raw": number, "default_region": (region or settings.default_region)},
        "normalized": {
            "e164": normalized.e164,
            "international": normalized.international,
            "national": normalized.national,
            "region": normalized.region,
            "country_code": normalized.country_code,
        },
        "enrichment": {
            "carrier": enrichment.carrier,
            "region_name": enrichment.region_name,
            "time_zones": enrichment.time_zones,
            "number_type": enrichment.number_type,
            "iso_country_code": enrichment.iso_country_code,
            "dialing_prefix": enrichment.dialing_prefix,
        },
        "reputation": {
            "adapter_errors": adapter_errors,
        },
        "evidence": [r.to_dict() for r in evidence],
        "signals": {
            "found_in_scam_db": found_in_scam_db,
            "voip": voip,
            **domain_signals,
        },
        "score": score.to_dict(),
        "summary": {
            "executive_summary": exec_summary,
            "legal_disclaimer": LEGAL_DISCLAIMER,
        },
    }
    return report


def _print_human(report: dict[str, Any]) -> None:
    click.echo(_human_text(report), nl=False)


def _human_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("phoneint (lawful/ethical OSINT only)")
    lines.append(LEGAL_DISCLAIMER)
    lines.append("")

    n = report.get("normalized", {})
    e = report.get("enrichment", {})
    s = report.get("score", {})

    lines.append("Normalized:")
    lines.append(f"  E.164: {n.get('e164', '')}")
    lines.append(f"  International: {n.get('international', '')}")
    lines.append(f"  National: {n.get('national', '')}")
    lines.append(f"  Region: {n.get('region', '')}")
    lines.append("")

    lines.append("Enrichment:")
    lines.append(f"  Carrier: {e.get('carrier', '')}")
    lines.append(f"  Region name: {e.get('region_name', '')}")
    lines.append(f"  Time zones: {', '.join(e.get('time_zones', []) or [])}")
    lines.append(f"  Type: {e.get('number_type', '')}")
    lines.append("")

    lines.append("Risk score:")
    lines.append(f"  Score: {s.get('score', '')}/100")
    lines.append("")

    adapter_errors = (report.get("reputation", {}) or {}).get("adapter_errors", {})
    if isinstance(adapter_errors, dict) and adapter_errors:
        lines.append("Adapter errors:")
        for k, v in adapter_errors.items():
            lines.append(f"  - {k}: {v}")
        lines.append("")

    evidence = report.get("evidence", [])
    if isinstance(evidence, list) and evidence:
        lines.append("Evidence (top 5):")
        for item in evidence[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(f"  - [{item.get('source','')}] {item.get('title','')}")
            if item.get("url"):
                lines.append(f"    {item.get('url')}")

    return "\n".join(lines) + "\n"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def main() -> None:
    """Phone Number OSINT (lawful/ethical use only)."""


@main.command("lookup")
@click.argument("number", type=str)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write primary output to a file.",
)
@click.option(
    "--adapters",
    default="duckduckgo,public",
    show_default=True,
    help="Comma-separated adapter list: duckduckgo,google,public",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON report to stdout (or --output).")
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write full JSON report to a file.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML config path.",
)
@click.option(
    "--region", default=None, help="Default region (ISO alpha-2) used if NUMBER is not in E.164."
)
@click.option("--no-cache", is_flag=True, help="Disable SQLite cache.")
def lookup_cmd(
    number: str,
    output_path: Path | None,
    adapters: str,
    as_json: bool,
    report_path: Path | None,
    config_path: Path | None,
    region: str | None,
    no_cache: bool,
) -> None:
    """
    Lookup a phone number (parse, enrich, and run adapters).
    """

    settings = load_settings(yaml_path=config_path)
    configure_logging(level=settings.log_level, json_logging=settings.json_logging)

    adapter_names = _parse_adapters_csv(adapters)

    try:
        report = asyncio.run(
            lookup_async(
                number, settings=settings, adapters=adapter_names, region=region, no_cache=no_cache
            )
        )
    except MissingCountryError as exc:
        raise click.ClickException(str(exc)) from exc
    except InvalidPhoneNumberError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(f"{type(exc).__name__}: {exc}") from exc

    if report_path is not None:
        export_json(report, report_path)

    if as_json:
        payload = json.dumps(report, indent=2, sort_keys=True)
        if output_path is not None:
            output_path.write_text(payload, encoding="utf-8")
        else:
            click.echo(payload)
    else:
        if output_path is not None:
            # Human-readable output to file.
            output_path.write_text(_human_text(report), encoding="utf-8")
        _print_human(report)


@main.command("report")
@click.argument("input_report", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv", "pdf"], case_sensitive=False),
    default="csv",
)
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None)
def report_cmd(input_report: Path, fmt: str, output_path: Path | None) -> None:
    """
    Export an existing JSON report into CSV/PDF (or re-write JSON).
    """

    report = json.loads(input_report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise click.ClickException("Input report must be a JSON object.")

    if output_path is None:
        suffix = {"json": ".json", "csv": ".csv", "pdf": ".pdf"}[fmt.lower()]
        output_path = input_report.with_suffix(suffix)

    if fmt.lower() == "json":
        export_json(report, output_path)
    elif fmt.lower() == "csv":
        export_csv(report, output_path)
    elif fmt.lower() == "pdf":
        generate_pdf(report, output_path)
    else:
        raise click.ClickException(f"Unsupported format: {fmt}")

    click.echo(str(output_path))


@main.command("serve-gui")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML config path.",
)
def serve_gui_cmd(config_path: Path | None) -> None:
    """Launch the (optional) PySide6 GUI."""

    settings = load_settings(yaml_path=config_path)
    configure_logging(level=settings.log_level, json_logging=settings.json_logging)

    try:
        from phoneint.gui import run_gui
    except Exception as exc:
        raise click.ClickException(
            "GUI dependencies not installed. Install with `pip install 'phoneint[gui]'`."
        ) from exc

    run_gui(settings)
