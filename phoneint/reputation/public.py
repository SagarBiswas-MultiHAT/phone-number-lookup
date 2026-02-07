# file: phoneint/reputation/public.py
"""
Public reputation checks based on user-provided datasets.

This module ships with a small sample dataset (`phoneint/data/scam_list.json`)
purely for tests and demos. For real investigations, replace/extend with
datasets you have lawful rights to use.

Important:
    Do NOT scrape or bypass authentication for private services (e.g., Truecaller).
    If you integrate a third-party service, ensure you have explicit permission
    and follow its Terms of Service.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

from phoneint.reputation.adapter import ReputationAdapter, SearchResult, now_utc


@dataclass(frozen=True, slots=True)
class ScamEntry:
    e164: str
    label: str
    source: str
    reference_url: str
    last_seen: date | None = None
    notes: str = ""


def _parse_entry(obj: dict[str, object]) -> ScamEntry:
    e164 = str(obj.get("e164") or "")
    label = str(obj.get("label") or "")
    source = str(obj.get("source") or "unknown")
    reference_url = str(obj.get("reference_url") or f"scamdb://{source}")
    last_seen_raw = obj.get("last_seen")
    last_seen: date | None = None
    if isinstance(last_seen_raw, str) and last_seen_raw:
        try:
            last_seen = date.fromisoformat(last_seen_raw)
        except ValueError:
            last_seen = None
    notes = str(obj.get("notes") or "")
    return ScamEntry(
        e164=e164,
        label=label,
        source=source,
        reference_url=reference_url,
        last_seen=last_seen,
        notes=notes,
    )


def load_scam_list(path: Path | None = None) -> list[ScamEntry]:
    """Load scam-list entries, defaulting to the packaged sample dataset."""

    data: str | None = None
    if path is not None:
        try:
            if path.exists():
                raw_text = path.read_text(encoding="utf-8")
                if raw_text.strip():
                    data = raw_text
        except OSError:
            data = None

    if data is None:
        data = (
            resources.files("phoneint.data").joinpath("scam_list.json").read_text(encoding="utf-8")
        )

    raw = json.loads(data)
    if not isinstance(raw, list):
        raise ValueError("scam_list.json must contain a JSON array")

    entries: list[ScamEntry] = []
    for item in raw:
        if isinstance(item, dict):
            entries.append(_parse_entry(item))
    return entries


def check_scam_list(e164: str, entries: list[ScamEntry], *, limit: int = 5) -> list[SearchResult]:
    """
    Check an E.164 number against scam-list entries and return evidence results.
    """

    ts = now_utc()
    matches = [e for e in entries if e.e164 == e164]
    out: list[SearchResult] = []
    for m in matches[:limit]:
        snippet_parts: list[str] = []
        if m.last_seen is not None:
            snippet_parts.append(f"last_seen={m.last_seen.isoformat()}")
        if m.notes:
            snippet_parts.append(m.notes)
        snippet = " | ".join(snippet_parts)
        out.append(
            SearchResult(
                title=m.label,
                url=m.reference_url,
                snippet=snippet,
                timestamp=ts,
                source="public_scam_db",
            )
        )
    return out


class PublicScamListAdapter(ReputationAdapter):
    """Reputation adapter backed by a JSON dataset (scam list)."""

    name = "public_scam_db"

    def __init__(self, *, scam_list_path: Path | None = None) -> None:
        self._entries = load_scam_list(scam_list_path)

    async def check(self, e164: str, *, limit: int = 5) -> list[SearchResult]:
        return check_scam_list(e164, self._entries, limit=limit)
