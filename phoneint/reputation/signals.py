from __future__ import annotations

import json
from pathlib import Path

from phoneint.reputation.adapter import SearchResult, now_utc

SIGNAL_NAMES = (
    "voip",
    "found_in_classifieds",
    "business_listing",
)

DEFAULT_SIGNAL_OVERRIDES_PATH = Path("phoneint/data/signal_overrides.json")

SIGNAL_DISPLAY_NAMES = {
    "voip": "VoIP signal",
    "found_in_classifieds": "classifieds mention",
    "business_listing": "business directory mention",
}


def _normalize_number(value: str) -> str:
    return value.strip()


def load_signal_overrides(path: Path | None) -> dict[str, frozenset[str]]:
    """Return configured override E.164 numbers for each signal."""

    overrides: dict[str, frozenset[str]] = {name: frozenset() for name in SIGNAL_NAMES}
    if path is None or not path.exists():
        return overrides

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return overrides

    if not isinstance(raw, dict):
        return overrides

    for name in SIGNAL_NAMES:
        values = raw.get(name)
        if isinstance(values, list) or isinstance(values, tuple):
            cleaned: list[str] = []
            for value in values:
                normalized_value = _normalize_number(str(value))
                if normalized_value:
                    cleaned.append(normalized_value)
            overrides[name] = frozenset(cleaned)
    return overrides


def apply_signal_overrides(
    *,
    e164: str,
    number_type: str,
    domain_signals: dict[str, bool],
    overrides: dict[str, frozenset[str]],
) -> tuple[bool, dict[str, bool], dict[str, bool]]:
    """Return signals merged with any configured overrides."""

    merged = {name: bool(domain_signals.get(name)) for name in domain_signals}
    hits: dict[str, bool] = {name: False for name in SIGNAL_NAMES}

    voip_from_type = number_type == "voip"
    hits["voip"] = e164 in overrides.get("voip", frozenset())
    voip_signal = voip_from_type or hits["voip"]

    for name in ("found_in_classifieds", "business_listing"):
        if e164 in overrides.get(name, frozenset()):
            merged[name] = True
            hits[name] = True

    return voip_signal, merged, hits


def generate_signal_override_evidence(e164: str, hits: dict[str, bool]) -> list[SearchResult]:
    """Return synthetic evidence entries for any fired signal overrides."""

    entries: list[SearchResult] = []
    for name in SIGNAL_NAMES:
        if not hits.get(name):
            continue
        label = SIGNAL_DISPLAY_NAMES.get(name, name)
        entries.append(
            SearchResult(
                title=f"Signal override: {label}",
                url="",
                snippet=f"Configured override flagged the {label} for {e164}.",
                timestamp=now_utc(),
                source="signal_override",
            )
        )
    return entries
