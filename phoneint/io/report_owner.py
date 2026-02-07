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
                "label": "",
                "url": _safe_str(item.get("url")),
                "snippet": _safe_str(item.get("snippet")),
                "timestamp": _safe_str(item.get("timestamp")),
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
                "section": "owner_intel",
                "key": "association",
                "value": "",
                "source": _safe_str(item.get("source")),
                "title": "",
                "label": _safe_str(item.get("label")),
                "url": _safe_str(item.get("url")),
                "snippet": _safe_str(item.get("snippet")),
                "timestamp": _safe_str(item.get("timestamp")),
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
                "section": "owner_audit",
                "key": "audit",
                "value": "",
                "source": "",
                "title": "",
                "label": "",
                "url": "",
                "snippet": "",
                "timestamp": _safe_str(item.get("time")),
                "adapter": _safe_str(item.get("adapter")),
                "result": _safe_str(item.get("result")),
                "caller": _safe_str(item.get("caller")),
                "legal_basis": json.dumps(legal_basis, ensure_ascii=True)
                if legal_basis is not None
                else "",
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
                "label": "",
                "url": "",
                "snippet": "",
                "timestamp": "",
                "adapter": "",
                "result": "",
                "caller": "",
                "legal_basis": "",
            }
        )
    return rows


def export_csv(report: Mapping[str, Any], path: Path) -> None:
    """
    Export owner report as a structured CSV for easier review.

    Includes key/value summary, owner intel rows, and audit trail rows.
    """

    fieldnames = [
        "row_index",
        "row_type",
        "section",
        "key",
        "value",
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

    rows: list[dict[str, str]] = []
    rows.extend(_iter_kv_rows("metadata", report.get("metadata")))
    rows.extend(_iter_kv_rows("query", report.get("query")))
    rows.extend(_iter_kv_rows("normalized", report.get("normalized")))

    owner_intel = report.get("owner_intel")
    if isinstance(owner_intel, dict):
        rows.extend(_iter_kv_rows("owner_intel", owner_intel))

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
                "label": "",
                "url": "",
                "snippet": "",
                "timestamp": "",
                "adapter": "",
                "result": "",
                "caller": "",
                "legal_basis": "",
            }
        )

    rows.extend(_iter_evidence_rows(report))
    rows.extend(_iter_owner_association_rows(report))
    rows.extend(_iter_owner_audit_rows(report))

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            row["row_index"] = str(idx)
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

    heading("phoneint owner intelligence report")

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
    normalized = report.get("normalized", {})
    if isinstance(normalized, dict):
        key_value("E164", normalized.get("e164", ""))
        key_value("Region", normalized.get("region", ""))

    owner_intel = report.get("owner_intel", {})
    if isinstance(owner_intel, dict):
        paragraph("")
        heading("Owner intelligence")
        key_value("Ownership type", owner_intel.get("ownership_type", ""))
        key_value("Confidence", owner_intel.get("confidence_score", ""))
        key_value("PII allowed", owner_intel.get("pii_allowed", ""))

        pii = owner_intel.get("pii")
        if isinstance(pii, dict):
            key_value("PII", f"{_safe_str(pii.get('name'))} ({_safe_str(pii.get('source'))})")

        signals = owner_intel.get("signals")
        if isinstance(signals, dict) and signals:
            paragraph("")
            heading("Signals")
            for key in sorted(signals.keys()):
                key_value(key, signals.get(key))

        associations = owner_intel.get("associations")
        if isinstance(associations, list) and associations:
            paragraph("")
            heading("Associations")
            for assoc in associations:
                if not isinstance(assoc, dict):
                    continue
                label = _safe_str(assoc.get("label"))
                source = _safe_str(assoc.get("source"))
                snippet = _safe_str(assoc.get("snippet"))
                paragraph(f"- [{label}] {source}")
                if assoc.get("url"):
                    paragraph(f"  {_safe_str(assoc.get('url'))}")
                if snippet:
                    paragraph(f"  {snippet}")
        else:
            paragraph("")
            heading("Associations")
            paragraph("No owner associations found.")
    else:
        paragraph("")
        heading("Owner intelligence")
        paragraph("No owner intelligence available.")

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

    audit = report.get("owner_audit_trail")
    if isinstance(audit, list) and audit:
        paragraph("")
        heading("Audit trail")
        for item in audit:
            if not isinstance(item, dict):
                continue
            adapter = _safe_str(item.get("adapter", ""))
            result = _safe_str(item.get("result", ""))
            time = _safe_str(item.get("time", ""))
            paragraph(f"- {adapter}: {result} {time}")
    else:
        paragraph("")
        heading("Audit trail")
        paragraph("No audit records available.")

    paragraph("")
    heading("Legal disclaimer")
    paragraph(LEGAL_DISCLAIMER)

    c.save()


__all__ = ["export_csv", "export_json", "generate_pdf"]
