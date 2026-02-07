# file: phoneint/io/report_owner.py
"""Owner intelligence report export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from phoneint.io.report import LEGAL_DISCLAIMER


def export_json(report: Mapping[str, Any], path: Path) -> None:
    """Write the full report to disk as JSON."""

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
                "row_type": "evidence",
                "source": str(item.get("source") or ""),
                "title": str(item.get("title") or ""),
                "label": "",
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("snippet") or ""),
                "timestamp": str(item.get("timestamp") or ""),
                "adapter": "",
                "result": "",
                "caller": "",
                "legal_basis": "",
            }
        )
    return rows


def _iter_owner_association_rows(report: Mapping[str, Any]) -> Iterable[dict[str, str]]:
    owner_intel = report.get("owner_intel")
    if not isinstance(owner_intel, dict):
        return []
    associations = owner_intel.get("associations")
    if not isinstance(associations, list):
        return []
    rows: list[dict[str, str]] = []
    for item in associations:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "row_type": "owner_association",
                "source": str(item.get("source") or ""),
                "title": "",
                "label": str(item.get("label") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("snippet") or ""),
                "timestamp": str(item.get("timestamp") or ""),
                "adapter": "",
                "result": "",
                "caller": "",
                "legal_basis": "",
            }
        )
    return rows


def _iter_owner_audit_rows(report: Mapping[str, Any]) -> Iterable[dict[str, str]]:
    audit = report.get("owner_audit_trail")
    if not isinstance(audit, list):
        return []
    rows: list[dict[str, str]] = []
    for item in audit:
        if not isinstance(item, dict):
            continue
        legal_basis = item.get("legal_basis")
        rows.append(
            {
                "row_type": "owner_audit",
                "source": "",
                "title": "",
                "label": "",
                "url": "",
                "snippet": "",
                "timestamp": str(item.get("time") or ""),
                "adapter": str(item.get("adapter") or ""),
                "result": str(item.get("result") or ""),
                "caller": str(item.get("caller") or ""),
                "legal_basis": json.dumps(legal_basis) if legal_basis is not None else "",
            }
        )
    return rows


def export_csv(report: Mapping[str, Any], path: Path) -> None:
    """
    Export evidence, owner associations, and audit trail as CSV.

    This produces a long table across all owner-related records.
    """

    fieldnames = [
        "row_type",
        "source",
        "title",
        "label",
        "url",
        "snippet",
        "timestamp",
        "adapter",
        "result",
        "caller",
        "legal_basis",
    ]
    rows = [
        *_iter_evidence_rows(report),
        *_iter_owner_association_rows(report),
        *_iter_owner_audit_rows(report),
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def generate_pdf(report: Mapping[str, Any], path: Path) -> None:
    """
    Generate a PDF summary for owner intelligence.

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
    _ = width
    x = 0.75 * inch
    y = height - 0.75 * inch

    def line(txt: str, *, dy: float = 14.0, bold: bool = False) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if not bold else 11)
        c.drawString(x, y, txt[:180])
        y -= dy
        if y < 0.75 * inch:
            c.showPage()
            y = height - 0.75 * inch

    line("phoneint owner intelligence report", bold=True, dy=18)

    meta = report.get("metadata", {})
    if isinstance(meta, dict):
        line(f"Generated at: {meta.get('generated_at', '')}")
        line(f"Version: {meta.get('version', '')}")

    owner_intel = report.get("owner_intel", {})
    if isinstance(owner_intel, dict):
        line("")
        line("Owner intelligence:", bold=True)
        line(f"Ownership type: {owner_intel.get('ownership_type', '')}")
        line(f"Confidence: {owner_intel.get('confidence_score', '')}")
        line(f"PII allowed: {owner_intel.get('pii_allowed', '')}")
        pii = owner_intel.get("pii")
        if isinstance(pii, dict):
            line(f"PII: {pii.get('name', '')} ({pii.get('source', '')})")

        signals = owner_intel.get("signals")
        if isinstance(signals, dict) and signals:
            line("")
            line("Signals:", bold=True)
            for key in sorted(signals.keys()):
                line(f"- {key}: {signals[key]}")

        associations = owner_intel.get("associations")
        if isinstance(associations, list) and associations:
            line("")
            line("Associations:", bold=True)
            for assoc in associations[:12]:
                if not isinstance(assoc, dict):
                    continue
                label = assoc.get("label", "")
                source = assoc.get("source", "")
                snippet = str(assoc.get("snippet") or "")
                if len(snippet) > 120:
                    snippet = f"{snippet[:117]}..."
                line(f"- [{label}] {source}: {snippet}")

    audit = report.get("owner_audit_trail")
    if isinstance(audit, list) and audit:
        line("")
        line("Audit trail:", bold=True)
        for item in audit[:10]:
            if not isinstance(item, dict):
                continue
            adapter = item.get("adapter", "")
            result = item.get("result", "")
            time = item.get("time", "")
            line(f"- {adapter}: {result} {time}")

    line("")
    line("Legal disclaimer:", bold=True)
    line(LEGAL_DISCLAIMER)

    c.save()


__all__ = ["export_csv", "export_json", "generate_pdf"]
