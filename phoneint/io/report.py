# file: phoneint/io/report.py
"""
Report generation and export helpers.

Reports are plain dictionaries (JSON-serializable). This keeps report formats
stable and tool-agnostic (CLI, GUI, API).

PDF generation is optional and requires extra dependencies.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

LEGAL_DISCLAIMER = (
    "This tool is for lawful, ethical OSINT research only. Do not use it to harass, "
    "stalk, dox, or violate privacy. Always comply with applicable laws and Terms of Service."
)


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def export_json(report: Mapping[str, Any], path: Path) -> None:
    """Write a report to disk as pretty-printed JSON."""

    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=True)


def _iter_evidence_rows(report: Mapping[str, Any]) -> Iterable[dict[str, str]]:
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        return []
    rows: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "row_type": "evidence",
                "section": "evidence",
                "key": "",
                "value": "",
                "source": _safe_str(item.get("source")),
                "title": _safe_str(item.get("title")),
                "url": _safe_str(item.get("url")),
                "snippet": _safe_str(item.get("snippet")),
                "timestamp": _safe_str(item.get("timestamp")),
                "contribution": "",
                "reason": "",
                "weight": "",
            }
        )
    return rows


def _iter_kv_rows(
    section: str, data: Mapping[str, Any] | None
) -> Iterable[dict[str, str]]:
    if not isinstance(data, dict):
        return []
    rows: list[dict[str, str]] = []
    for key in sorted(data.keys()):
        rows.append(
            {
                "row_type": "kv",
                "section": section,
                "key": _safe_str(key),
                "value": _safe_str(data.get(key)),
                "source": "",
                "title": "",
                "url": "",
                "snippet": "",
                "timestamp": "",
                "contribution": "",
                "reason": "",
                "weight": "",
            }
        )
    return rows


def export_csv(report: Mapping[str, Any], path: Path) -> None:
    """
    Export report as a structured CSV for easier review.

    The CSV includes a key/value summary and separate evidence rows.
    """

    fieldnames = [
        "row_index",
        "row_type",
        "section",
        "key",
        "value",
        "source",
        "title",
        "url",
        "snippet",
        "timestamp",
        "contribution",
        "reason",
        "weight",
    ]

    rows: list[dict[str, str]] = []
    rows.extend(_iter_kv_rows("metadata", report.get("metadata")))
    rows.extend(_iter_kv_rows("query", report.get("query")))
    rows.extend(_iter_kv_rows("normalized", report.get("normalized")))
    rows.extend(_iter_kv_rows("enrichment", report.get("enrichment")))
    rows.extend(_iter_kv_rows("signals", report.get("signals")))
    rows.extend(_iter_kv_rows("signal_overrides", report.get("signal_overrides")))

    summary = report.get("summary")
    if isinstance(summary, dict):
        rows.extend(_iter_kv_rows("summary", summary))
    else:
        rows.append(
            {
                "row_type": "kv",
                "section": "summary",
                "key": "legal_disclaimer",
                "value": LEGAL_DISCLAIMER,
                "source": "",
                "title": "",
                "url": "",
                "snippet": "",
                "timestamp": "",
                "contribution": "",
                "reason": "",
                "weight": "",
            }
        )

    score = report.get("score")
    if isinstance(score, dict):
        rows.extend(_iter_kv_rows("score", {"score": score.get("score")}))
        breakdown = score.get("breakdown")
        if isinstance(breakdown, list):
            for item in breakdown:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "row_type": "score_breakdown",
                        "section": "score",
                        "key": _safe_str(item.get("name")),
                        "value": _safe_str(item.get("contribution")),
                        "source": "",
                        "title": "",
                        "url": "",
                        "snippet": "",
                        "timestamp": "",
                        "contribution": _safe_str(item.get("contribution")),
                        "reason": _safe_str(item.get("reason")),
                        "weight": _safe_str(item.get("weight")),
                    }
                )

    rows.extend(_iter_evidence_rows(report))

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            row["row_index"] = str(idx)
            writer.writerow(row)


def generate_pdf(report: Mapping[str, Any], path: Path) -> None:
    """
    Generate a simple PDF report.

    Requires:
        `reportlab` (install with `pip install 'phoneint[pdf]'`)
    """

    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover (optional dependency)
        raise RuntimeError(
            "PDF generation requires `reportlab`. Install with `pip install 'phoneint[pdf]'`."
        ) from exc

    c = canvas.Canvas(str(path), pagesize=LETTER)
    width, height = LETTER
    x = 0.75 * inch
    y = height - 0.75 * inch
    max_width = width - (1.5 * inch)

    def _new_page() -> None:
        nonlocal y
        c.showPage()
        y = height - 0.75 * inch

    def _draw_lines(lines: list[str], *, font: str, size: int, leading: float) -> None:
        nonlocal y
        c.setFont(font, size)
        for txt in lines:
            if y < 0.75 * inch:
                _new_page()
                c.setFont(font, size)
            c.drawString(x, y, txt)
            y -= leading

    def _wrap_text(text: str, *, font: str, size: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def heading(text: str) -> None:
        _draw_lines([text], font="Helvetica-Bold", size=12, leading=16)

    def paragraph(text: str) -> None:
        lines = _wrap_text(text, font="Helvetica", size=10)
        _draw_lines(lines, font="Helvetica", size=10, leading=13)

    def key_value(label: str, value: Any) -> None:
        paragraph(f"{label}: {_safe_str(value)}")

    heading("phoneint report")

    meta = report.get("metadata", {})
    if isinstance(meta, dict):
        key_value("Generated at", meta.get("generated_at", ""))
        key_value("Version", meta.get("version", ""))

    paragraph("")
    heading("Overview")
    query = report.get("query", {})
    if isinstance(query, dict):
        key_value("Query", query.get("raw", ""))
        key_value("Default region", query.get("default_region", ""))
    score = report.get("score", {})
    if isinstance(score, dict):
        key_value("Score", score.get("score", ""))
    evidence_count = len(report.get("evidence", []) or [])
    key_value("Evidence items", evidence_count)

    summary = report.get("summary", {})
    if isinstance(summary, dict):
        paragraph("")
        heading("Executive summary")
        paragraph(_safe_str(summary.get("executive_summary") or ""))

    paragraph("")
    heading("Legal disclaimer")
    paragraph(LEGAL_DISCLAIMER)

    normalized = report.get("normalized", {})
    if isinstance(normalized, dict):
        paragraph("")
        heading("Normalized")
        for k in ("e164", "international", "national", "region", "country_code"):
            key_value(k, normalized.get(k, ""))

    enrichment = report.get("enrichment", {})
    if isinstance(enrichment, dict):
        paragraph("")
        heading("Enrichment")
        for k in ("carrier", "region_name", "number_type", "iso_country_code", "dialing_prefix"):
            key_value(k, enrichment.get(k, ""))
        time_zones = enrichment.get("time_zones") or []
        if isinstance(time_zones, list) and time_zones:
            key_value("time_zones", ", ".join(str(t) for t in time_zones))

    signals = report.get("signals", {})
    if isinstance(signals, dict):
        paragraph("")
        heading("Signals")
        for key in sorted(signals.keys()):
            key_value(key, signals.get(key, ""))

    overrides = report.get("signal_overrides", {})
    if isinstance(overrides, dict) and overrides:
        paragraph("")
        heading("Signal overrides")
        for key in sorted(overrides.keys()):
            key_value(key, overrides.get(key, ""))

    score = report.get("score", {})
    if isinstance(score, dict):
        paragraph("")
        heading("Risk score")
        key_value("Score", score.get("score", ""))
        breakdown = score.get("breakdown")
        if isinstance(breakdown, list) and breakdown:
            paragraph("")
            heading("Score breakdown")
            for b in breakdown:
                if not isinstance(b, dict):
                    continue
                label = f"{_safe_str(b.get('name'))}: {_safe_str(b.get('contribution'))}"
                reason = _safe_str(b.get("reason") or "")
                paragraph(f"- {label} ({reason})")

    adapter_errors = (report.get("reputation", {}) or {}).get("adapter_errors", {})
    if isinstance(adapter_errors, dict) and adapter_errors:
        paragraph("")
        heading("Adapter errors")
        for key in sorted(adapter_errors.keys()):
            paragraph(f"- {key}: {_safe_str(adapter_errors.get(key))}")

    evidence_rows = list(_iter_evidence_rows(report))
    if evidence_rows:
        paragraph("")
        heading("Evidence")
        for r in evidence_rows:
            title = r.get("title", "")
            source = r.get("source", "")
            paragraph(f"- [{source}] {title}")
            if r.get("url"):
                paragraph(f"  {r['url']}")
            if r.get("snippet"):
                paragraph(f"  {r['snippet']}")
    else:
        paragraph("")
        heading("Evidence")
        paragraph("No evidence items found.")

    c.save()
