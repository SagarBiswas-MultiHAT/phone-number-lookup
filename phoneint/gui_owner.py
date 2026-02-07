# file: phoneint/gui_owner.py
"""Owner intelligence panel for the GUI."""

from __future__ import annotations

from typing import Any, Protocol


class OwnerIntelPanelProtocol(Protocol):
    def reset(self) -> None: ...

    def consent_obtained(self) -> bool: ...

    def legal_purpose(self) -> str: ...

    def set_owner_intel(
        self, owner_intel: dict[str, Any], owner_audit: list[dict[str, Any]]
    ) -> None: ...


def create_owner_intel_panel(*, pii_capable_available: bool) -> OwnerIntelPanelProtocol:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QCheckBox,
            QFormLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QVBoxLayout,
            QWidget,
        )
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "GUI dependencies not installed. Install with `pip install 'phoneint[gui]'`."
        ) from exc

    class OwnerIntelPanel(QWidget):
        def __init__(self, *, pii_capable_available: bool) -> None:
            super().__init__()
            self._pii_capable_available = pii_capable_available

            root = QVBoxLayout()

            consent_row = QHBoxLayout()
            self._consent_checkbox = QCheckBox(
                "I confirm lawful basis and explicit consent for PII lookups"
            )
            self._consent_checkbox.setEnabled(self._pii_capable_available)
            consent_row.addWidget(self._consent_checkbox)

            self._consent_status = QLabel()
            self._consent_status.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            consent_row.addWidget(self._consent_status, 1)
            root.addLayout(consent_row)

            purpose_row = QHBoxLayout()
            purpose_row.addWidget(QLabel("Purpose"))
            self._purpose_input = QLineEdit()
            self._purpose_input.setPlaceholderText("customer-verification")
            self._purpose_input.setEnabled(self._pii_capable_available)
            purpose_row.addWidget(self._purpose_input, 1)
            root.addLayout(purpose_row)

            summary_box = QGroupBox("Summary")
            summary_layout = QFormLayout()
            self._ownership_label = QLabel("-")
            self._confidence_label = QLabel("-")
            self._pii_label = QLabel("-")
            summary_layout.addRow("Ownership type", self._ownership_label)
            summary_layout.addRow("Confidence", self._confidence_label)
            summary_layout.addRow("PII", self._pii_label)
            summary_box.setLayout(summary_layout)
            root.addWidget(summary_box)

            signals_box = QGroupBox("Signals")
            signals_layout = QVBoxLayout()
            self._signals_list = QListWidget()
            signals_layout.addWidget(self._signals_list)
            signals_box.setLayout(signals_layout)
            root.addWidget(signals_box)

            assoc_box = QGroupBox("Associations")
            assoc_layout = QVBoxLayout()
            self._associations_list = QListWidget()
            assoc_layout.addWidget(self._associations_list)
            assoc_box.setLayout(assoc_layout)
            root.addWidget(assoc_box)

            audit_box = QGroupBox("Audit Trail")
            audit_layout = QVBoxLayout()
            self._audit_list = QListWidget()
            audit_layout.addWidget(self._audit_list)
            audit_box.setLayout(audit_layout)
            root.addWidget(audit_box)

            if not self._pii_capable_available:
                self._consent_status.setText("PII adapter not enabled")
                self._consent_status.setStyleSheet("color: #a33;")
            else:
                self._consent_status.setText("PII adapter available")
                self._consent_status.setStyleSheet("color: #060;")

            self.setLayout(root)

        def reset(self) -> None:
            self._consent_checkbox.setChecked(False)
            self._purpose_input.clear()
            self._ownership_label.setText("-")
            self._confidence_label.setText("-")
            self._pii_label.setText("-")
            self._signals_list.clear()
            self._associations_list.clear()
            self._audit_list.clear()

        def consent_obtained(self) -> bool:
            return bool(self._pii_capable_available and self._consent_checkbox.isChecked())

        def legal_purpose(self) -> str:
            return str(self._purpose_input.text()).strip()

        def set_owner_intel(
            self, owner_intel: dict[str, Any], owner_audit: list[dict[str, Any]]
        ) -> None:
            ownership_type = owner_intel.get("ownership_type")
            confidence = owner_intel.get("confidence_score")
            pii_allowed = owner_intel.get("pii_allowed")
            pii = owner_intel.get("pii")

            self._ownership_label.setText(str(ownership_type or "-"))
            self._confidence_label.setText("-" if confidence is None else f"{confidence}/100")

            if pii_allowed and isinstance(pii, dict):
                pii_name = pii.get("name") or "unknown"
                pii_source = pii.get("source") or "unknown"
                self._pii_label.setText(f"{pii_name} ({pii_source})")
            elif pii_allowed:
                self._pii_label.setText("allowed (no PII returned)")
            else:
                self._pii_label.setText("-" if pii is None else str(pii))

            self._signals_list.clear()
            signals = owner_intel.get("signals") or {}
            if isinstance(signals, dict):
                for key in sorted(signals.keys()):
                    self._signals_list.addItem(f"{key}: {signals[key]}")

            self._associations_list.clear()
            associations = owner_intel.get("associations") or []
            if isinstance(associations, list):
                for assoc in associations:
                    if not isinstance(assoc, dict):
                        continue
                    label = assoc.get("label") or "mention"
                    source = assoc.get("source") or "unknown"
                    snippet = assoc.get("snippet") or ""
                    snippet = snippet.replace("\n", " ").strip()
                    if len(snippet) > 120:
                        snippet = f"{snippet[:117]}..."
                    self._associations_list.addItem(f"[{label}] {source} - {snippet}")

            self._audit_list.clear()
            if isinstance(owner_audit, list):
                for record in owner_audit:
                    if not isinstance(record, dict):
                        continue
                    adapter = record.get("adapter") or "unknown"
                    result = record.get("result") or "unknown"
                    time = record.get("time") or ""
                    self._audit_list.addItem(f"{adapter}: {result} {time}")

    return OwnerIntelPanel(pii_capable_available=pii_capable_available)


__all__ = ["OwnerIntelPanelProtocol", "create_owner_intel_panel"]
