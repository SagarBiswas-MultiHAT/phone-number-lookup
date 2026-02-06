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
                "source": str(item.get("source") or ""),
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("snippet") or ""),
                "timestamp": str(item.get("timestamp") or ""),
            }
        )
    return rows


def export_csv(report: Mapping[str, Any], path: Path) -> None:
    """
    Export evidence items from a report as CSV.

    This produces a "long" table (one row per evidence item).
    """

    fieldnames = ["source", "title", "url", "snippet", "timestamp"]
    rows = list(_iter_evidence_rows(report))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
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
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover (optional dependency)
        raise RuntimeError(
            "PDF generation requires `reportlab`. Install with `pip install 'phoneint[pdf]'`."
        ) from exc

    c = canvas.Canvas(str(path), pagesize=LETTER)
    width, height = LETTER
    x = 0.75 * inch
    y = height - 0.75 * inch

    def line(txt: str, *, dy: float = 14.0, bold: bool = False) -> None:
        nonlocal y
        if bold:
            c.setFont("Helvetica-Bold", 11)
        else:
            c.setFont("Helvetica", 10)
        c.drawString(x, y, txt[:180])
        y -= dy
        if y < 0.75 * inch:
            c.showPage()
            y = height - 0.75 * inch

    line("phoneint report", bold=True, dy=18)

    meta = report.get("metadata", {})
    if isinstance(meta, dict):
        line(f"Generated at: {meta.get('generated_at', '')}")
        line(f"Version: {meta.get('version', '')}")

    summary = report.get("summary", {})
    if isinstance(summary, dict):
        line("")
        line("Executive summary:", bold=True)
        line(str(summary.get("executive_summary") or "")[:180])
        line("")
        line("Legal disclaimer:", bold=True)
        line(LEGAL_DISCLAIMER[:180])

    normalized = report.get("normalized", {})
    if isinstance(normalized, dict):
        line("")
        line("Normalized:", bold=True)
        for k in ("e164", "international", "national", "region", "country_code"):
            line(f"{k}: {normalized.get(k, '')}")

    score = report.get("score", {})
    if isinstance(score, dict):
        line("")
        line("Risk score:", bold=True)
        line(f"Score: {score.get('score', '')}")
        breakdown = score.get("breakdown")
        if isinstance(breakdown, list) and breakdown:
            line("Breakdown:", bold=True)
            for b in breakdown[:12]:
                if not isinstance(b, dict):
                    continue
                line(f"- {b.get('name', '')}: {b.get('contribution', '')} ({b.get('reason', '')})")

    evidence_rows = list(_iter_evidence_rows(report))
    if evidence_rows:
        line("")
        line("Evidence:", bold=True)
        for r in evidence_rows[:20]:
            line(f"- [{r['source']}] {r['title']}")
            if r["url"]:
                line(f"  {r['url']}")

    c.save()
