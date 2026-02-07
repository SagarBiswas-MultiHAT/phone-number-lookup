# file: phoneint/gui.py
"""
PySide6 GUI skeleton (non-blocking via qasync).

This GUI is intentionally minimal but functional:
- parse/enrich a number
- run selected adapters asynchronously
- show progress and evidence as results arrive

Install GUI dependencies:
    pip install 'phoneint[gui]'
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from PySide6.QtCore import QRect

from phoneint.cache import CachedReputationAdapter, SQLiteTTLCache
from phoneint.config import PhoneintSettings
from phoneint.core.enrich import enrich_number
from phoneint.core.parser import InvalidPhoneNumberError, MissingCountryError, parse_and_normalize
from phoneint.io.report import LEGAL_DISCLAIMER
from phoneint.net.http import PerHostRateLimiter, build_async_client
from phoneint.reputation.adapter import ReputationAdapter, SearchResult
from phoneint.reputation.duckduckgo import DuckDuckGoInstantAnswerAdapter
from phoneint.reputation.google import GoogleCustomSearchAdapter
from phoneint.reputation.public import PublicScamListAdapter
from phoneint.reputation.score import infer_domain_signals, score_risk
from phoneint.reputation.signals import (
    apply_signal_overrides,
    generate_signal_override_evidence,
    load_signal_overrides,
)

logger = logging.getLogger(__name__)


def run_gui(settings: PhoneintSettings) -> None:
    try:
        from PySide6.QtCore import QEvent, QTimer, Qt
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMessageBox,
            QFileDialog,
            QPushButton,
            QProgressBar,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
        from qasync import QEventLoop, asyncSlot
    except Exception as exc:  # pragma: no cover (optional dependency)
        raise RuntimeError(
            "GUI dependencies not installed. Install with `pip install 'phoneint[gui]'`."
        ) from exc

    import getpass

    from phoneint import __version__
    from phoneint.gui_owner import OwnerIntelPanelProtocol, create_owner_intel_panel
    from phoneint.io.report import utc_now_iso
    from phoneint.io.report_owner import export_csv as export_csv_owner
    from phoneint.io.report_owner import export_json as export_json_owner
    from phoneint.io.report_owner import generate_pdf as generate_pdf_owner
    from phoneint.owner.classify import classify as classify_owner
    from phoneint.owner.interface import LegalBasis
    from phoneint.owner.signals import (
        associations_from_evidence,
        extract_owner_signals,
        score_owner_confidence,
    )
    from phoneint.owner.signals import OwnerIntelEngine
    from phoneint.owner.truecaller_adapter import TruecallerAdapter

    class MainWindow(QWidget):
        def __init__(self, settings: PhoneintSettings) -> None:
            super().__init__()
            self._settings = settings
            self._signal_overrides = load_signal_overrides(self._settings.signal_overrides_path)
            self._tasks: set[asyncio.Task[Any]] = set()
            self._last_report: dict[str, Any] | None = None
            self._initial_geometry: "QRect | None" = None
            self._was_maximized = False

            self.setWindowTitle("phoneint (Phone Number OSINT)")

            root = QVBoxLayout()

            disclaimer = QLabel(LEGAL_DISCLAIMER)
            disclaimer.setWordWrap(True)
            disclaimer.setStyleSheet("color: #444;")
            root.addWidget(disclaimer)

            form = QGridLayout()
            form.addWidget(QLabel("Number"), 0, 0)
            self.number_input = QLineEdit()
            self.number_input.setPlaceholderText("+14155550100")
            form.addWidget(self.number_input, 0, 1)

            form.addWidget(QLabel("Default region"), 1, 0)
            self.region_input = QLineEdit()
            self.region_input.setPlaceholderText(self._settings.default_region or "US")
            form.addWidget(self.region_input, 1, 1)

            root.addLayout(form)

            adapters_box = QGroupBox("Adapters")
            adapters_layout = QHBoxLayout()
            self.cb_public = QCheckBox("public (dataset)")
            self.cb_public.setChecked(True)
            self.cb_ddg = QCheckBox("duckduckgo")
            self.cb_ddg.setChecked(True)
            self.cb_google = QCheckBox("google (GCS)")
            self.cb_google.setChecked(False)
            adapters_layout.addWidget(self.cb_public)
            adapters_layout.addWidget(self.cb_ddg)
            adapters_layout.addWidget(self.cb_google)
            adapters_box.setLayout(adapters_layout)
            root.addWidget(adapters_box)

            buttons = QHBoxLayout()
            self.lookup_btn = QPushButton("Lookup")
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setEnabled(False)
            buttons.addWidget(self.lookup_btn)
            buttons.addWidget(self.cancel_btn)
            root.addLayout(buttons)

            download_row = QHBoxLayout()
            download_row.addWidget(QLabel("Download report"))
            self.report_format = QComboBox()
            self.report_format.addItems(["json", "csv", "pdf"])
            download_row.addWidget(self.report_format)
            self.download_btn = QPushButton("Save")
            self.download_btn.setEnabled(False)
            download_row.addWidget(self.download_btn)
            download_row.addStretch(1)
            root.addLayout(download_row)

            self.progress = QProgressBar()
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            root.addWidget(self.progress)

            self.status = QLabel("Ready.")
            root.addWidget(self.status)

            panels = QHBoxLayout()
            self.results_text = QTextEdit()
            self.results_text.setReadOnly(True)
            panels.addWidget(self.results_text, 2)

            # Right side: tabs for evidence and owner intelligence.
            tabs = QTabWidget()

            self.evidence_list = QListWidget()
            tabs.addTab(self.evidence_list, "Evidence")

            pii_capable_available = bool(
                self._settings.enable_truecaller and self._settings.truecaller_api_key
            )
            owner_panel_widget = create_owner_intel_panel(
                pii_capable_available=pii_capable_available
            )
            self.owner_panel = cast(OwnerIntelPanelProtocol, owner_panel_widget)
            tabs.addTab(cast(QWidget, owner_panel_widget), "Owner Intelligence")

            panels.addWidget(tabs, 1)
            root.addLayout(panels)

            self.setLayout(root)

            self.lookup_btn.clicked.connect(self.on_lookup)
            self.cancel_btn.clicked.connect(self.on_cancel)
            self.download_btn.clicked.connect(self.on_download_report)

            QTimer.singleShot(0, self._initialize_geometry)

        def _initialize_geometry(self) -> None:
            self._center_on_screen()
            self._initial_geometry = self.geometry()

        def _center_on_screen(self) -> None:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            geo = screen.availableGeometry()
            frame = self.frameGeometry()
            frame.moveCenter(geo.center())
            self.move(frame.topLeft())

        def changeEvent(self, event: QEvent) -> None:
            if event.type() == QEvent.Type.WindowStateChange:
                is_max = bool(self.windowState() & Qt.WindowState.WindowMaximized)
                if self._was_maximized and not is_max and self._initial_geometry is not None:
                    self.setGeometry(self._initial_geometry)
                    self._center_on_screen()
                self._was_maximized = is_max
            super().changeEvent(event)

        def _set_busy(self, busy: bool) -> None:
            self.lookup_btn.setEnabled(not busy)
            self.cancel_btn.setEnabled(busy)

        def _cancel_tasks(self) -> None:
            for t in list(self._tasks):
                t.cancel()

        @asyncSlot()
        async def on_lookup(self) -> None:
            self._cancel_tasks()
            self._tasks.clear()
            self.evidence_list.clear()
            self.results_text.clear()
            self.owner_panel.reset()
            self._last_report = None
            self.download_btn.setEnabled(False)

            number = self.number_input.text().strip()
            region = self.region_input.text().strip().upper() or None
            self._set_busy(True)
            self.status.setText("Parsing...")

            try:
                parsed, normalized = parse_and_normalize(
                    number, default_region=region or self._settings.default_region
                )
            except MissingCountryError as exc:
                QMessageBox.warning(self, "Missing country", str(exc))
                self._set_busy(False)
                self.status.setText("Ready.")
                return
            except InvalidPhoneNumberError as exc:
                QMessageBox.warning(self, "Invalid number", str(exc))
                self._set_busy(False)
                self.status.setText("Ready.")
                return
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"{type(exc).__name__}: {exc}")
                self._set_busy(False)
                self.status.setText("Ready.")
                return

            enrichment = enrich_number(parsed)
            self.results_text.append(f"E.164: {normalized.e164}")
            self.results_text.append(f"International: {normalized.international}")
            self.results_text.append(f"National: {normalized.national}")
            self.results_text.append(f"Region (ISO): {normalized.region}")
            self.results_text.append(f"Country code: {normalized.country_code}")
            self.results_text.append("")
            self.results_text.append(f"Carrier: {enrichment.carrier}")
            self.results_text.append(f"Region: {enrichment.region_name}")
            self.results_text.append(f"Time zones: {', '.join(enrichment.time_zones)}")
            self.results_text.append(f"Type: {enrichment.number_type}")
            self.results_text.append(f"ISO country code: {enrichment.iso_country_code}")
            self.results_text.append(f"Dialing prefix: {enrichment.dialing_prefix}")
            self.results_text.append("")

            http_config = self._settings.http_config()
            rate_limiter = PerHostRateLimiter(
                rate_per_second=http_config.rate_limit_per_host_per_second
            )

            cache: SQLiteTTLCache | None = None
            if self._settings.cache_enabled:
                cache = SQLiteTTLCache(self._settings.cache_path)

            adapters: list[ReputationAdapter] = []
            self.status.setText("Preparing adapters...")
            async with build_async_client(http_config) as client:
                if self.cb_public.isChecked():
                    adapters.append(
                        PublicScamListAdapter(scam_list_path=self._settings.scam_list_path)
                    )
                if self.cb_ddg.isChecked():
                    adapters.append(
                        DuckDuckGoInstantAnswerAdapter(
                            client=client, http_config=http_config, rate_limiter=rate_limiter
                        )
                    )
                if self.cb_google.isChecked():
                    try:
                        adapters.append(
                            GoogleCustomSearchAdapter(
                                client=client,
                                http_config=http_config,
                                api_key=self._settings.gcs_api_key,
                                cx=self._settings.gcs_cx,
                                rate_limiter=rate_limiter,
                            )
                        )
                    except Exception as exc:
                        QMessageBox.warning(self, "Google disabled", str(exc))

                if cache is not None:
                    adapters = [
                        CachedReputationAdapter(
                            a, cache=cache, ttl_seconds=self._settings.cache_ttl_seconds
                        )
                        for a in adapters
                    ]

                self.progress.setRange(0, max(1, len(adapters)))
                self.progress.setValue(0)

                evidence: list[SearchResult] = []
                owner_audit: list[dict[str, Any]] = []
                owner_intel_final: dict[str, Any] | None = None
                adapter_errors: dict[str, str] = {}
                completed = 0

                async def run_one(adapter: ReputationAdapter) -> tuple[str, list[SearchResult]]:
                    res = await adapter.check(normalized.e164, limit=5)
                    return adapter.name, res

                task_map: dict[asyncio.Future[tuple[str, list[SearchResult]]], str] = {}
                for ad in adapters:
                    t = asyncio.create_task(run_one(ad))
                    self._tasks.add(t)
                    task_map[t] = ad.name

                self.status.setText("Running adapters...")
                try:
                    for fut in asyncio.as_completed(task_map.keys()):
                        name = task_map.get(fut, "unknown")
                        try:
                            name, results = await fut
                        except Exception as exc:
                            adapter_errors[name] = f"{type(exc).__name__}: {exc}"
                            completed += 1
                            self.progress.setValue(completed)
                            self.status.setText(
                                f"Adapter failed: {name} ({completed}/{len(adapters)})"
                            )
                            continue

                        completed += 1
                        self.progress.setValue(completed)
                        self.status.setText(
                            f"Adapter finished: {name} ({completed}/{len(adapters)})"
                        )
                        for r in results:
                            evidence.append(r)
                            self.evidence_list.addItem(f"[{r.source}] {r.title}")

                        # Live-update owner intelligence based on public evidence so far.
                        voip_flag = enrichment.number_type == "voip"
                        associations = associations_from_evidence(evidence)
                        ownership_type = classify_owner(
                            parsed, associations, voip_flag=voip_flag, pii=None
                        )
                        signals = extract_owner_signals(
                            evidence=evidence,
                            associations=associations,
                            voip_flag=voip_flag,
                            pii_present=False,
                        )
                        confidence = score_owner_confidence(
                            ownership_type,
                            signals,
                            weights=self._settings.owner_confidence_weights,
                        )
                        owner_intel_public: dict[str, Any] = {
                            "ownership_type": ownership_type,
                            "associations": [a.to_dict() for a in associations],
                            "signals": signals.to_dict(),
                            "confidence_score": confidence.score,
                            "confidence_breakdown": [b.to_dict() for b in confidence.breakdown],
                            "pii_allowed": False,
                        }
                        self.owner_panel.set_owner_intel(owner_intel_public, [])
                except asyncio.CancelledError:
                    self.status.setText("Cancelled.")
                    return
                finally:
                    self._tasks.clear()

                # Optional: run PII-capable owner adapter (gated by config + explicit consent).
                allow_pii = bool(self.owner_panel.consent_obtained())
                purpose = self.owner_panel.legal_purpose()
                if allow_pii and not purpose:
                    QMessageBox.warning(
                        self,
                        "Purpose required",
                        "Please enter a purpose before enabling PII-capable identity lookups.",
                    )
                    allow_pii = False

                if (
                    allow_pii
                    and self._settings.enable_truecaller
                    and self._settings.truecaller_api_key
                ):
                    legal_basis: LegalBasis = {"purpose": purpose, "consent_obtained": True}
                    caller = getpass.getuser()
                    try:
                        tc = TruecallerAdapter(
                            client=client,
                            http_config=http_config,
                            enabled=True,
                            api_key=self._settings.truecaller_api_key,
                            rate_limiter=rate_limiter,
                        )
                        engine = OwnerIntelEngine(
                            adapters=[tc], weights=self._settings.owner_confidence_weights
                        )

                        pii_task: asyncio.Task[Any] = asyncio.create_task(
                            engine.build(
                                normalized.e164,
                                parsed_number=parsed,
                                evidence=evidence,
                                voip_flag=enrichment.number_type == "voip",
                                allow_pii=True,
                                legal_basis=legal_basis,
                                caller=caller,
                            )
                        )
                        self._tasks.add(pii_task)
                        owner_result, audit_records = await pii_task
                        owner_intel_final = owner_result.to_dict()
                        owner_audit = [a.to_dict() for a in audit_records]
                    except PermissionError as exc:
                        QMessageBox.warning(self, "Consent required", str(exc))
                    except asyncio.CancelledError:
                        self.status.setText("Cancelled.")
                        return
                    except Exception as exc:
                        QMessageBox.warning(
                            self, "Owner adapter error", f"{type(exc).__name__}: {exc}"
                        )
                    finally:
                        self._tasks.clear()

                if owner_intel_final is not None:
                    self.owner_panel.set_owner_intel(owner_intel_final, owner_audit)

            # Score once all evidence is in.
            found_in_scam_db = any(r.source == "public_scam_db" for r in evidence)
            domain_signals = infer_domain_signals(evidence)
            voip, domain_signals, override_hits = apply_signal_overrides(
                e164=normalized.e164,
                number_type=enrichment.number_type,
                domain_signals=domain_signals,
                overrides=self._signal_overrides,
            )
            override_evidence = generate_signal_override_evidence(normalized.e164, override_hits)
            if override_evidence:
                evidence.extend(override_evidence)
                for entry in override_evidence:
                    self.evidence_list.addItem(f"[{entry.source}] {entry.title}")
            score = score_risk(
                found_in_scam_db=found_in_scam_db,
                voip=voip,
                found_in_classifieds=domain_signals["found_in_classifieds"],
                business_listing=domain_signals["business_listing"],
                age_of_first_mention_days=None,
                weights=self._settings.score_weights,
            )

            self.results_text.append(f"Risk score: {score.score}/100")
            self.results_text.append("")
            self.results_text.append("Breakdown:")
            for b in score.breakdown:
                self.results_text.append(f"- {b.name}: {b.contribution:.1f} ({b.reason})")

            self.results_text.append("")
            self.results_text.append("Signals:")
            self.results_text.append(f"- found_in_scam_db: {found_in_scam_db}")
            self.results_text.append(f"- voip: {voip}")
            self.results_text.append(
                f"- found_in_classifieds: {domain_signals.get('found_in_classifieds')}"
            )
            self.results_text.append(
                f"- business_listing: {domain_signals.get('business_listing')}"
            )

            if adapter_errors:
                self.results_text.append("")
                self.results_text.append("Adapter errors:")
                for name, msg in adapter_errors.items():
                    self.results_text.append(f"- {name}: {msg}")

            triggered_overrides = [name for name, fired in override_hits.items() if fired]
            if triggered_overrides:
                self.results_text.append("")
                self.results_text.append("Signal overrides:")
                for name in triggered_overrides:
                    self.results_text.append(f"- {name}")

            self.results_text.append(f"Evidence items: {len(evidence)}")

            report: dict[str, Any] = {
                "metadata": {
                    "tool": "phoneint",
                    "version": __version__,
                    "generated_at": utc_now_iso(),
                },
                "query": {
                    "raw": number,
                    "default_region": (region or self._settings.default_region),
                },
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
                "reputation": {"adapter_errors": adapter_errors},
                "evidence": [r.to_dict() for r in evidence],
                "owner_intel": owner_intel_final or {},
                "owner_audit_trail": owner_audit,
                "signals": {
                    "found_in_scam_db": found_in_scam_db,
                    "voip": voip,
                    **domain_signals,
                },
                "signal_overrides": override_hits,
                "score": score.to_dict(),
                "summary": {
                    "executive_summary": (
                        f"Risk score {score.score}/100. "
                        f"Matched scam dataset: {'yes' if found_in_scam_db else 'no'}. "
                        f"Evidence items: {len(evidence)}."
                    ),
                    "legal_disclaimer": LEGAL_DISCLAIMER,
                },
            }

            self._last_report = report
            self.download_btn.setEnabled(True)

            self._set_busy(False)
            self.status.setText("Done.")

        def on_cancel(self) -> None:
            self._cancel_tasks()
            self._set_busy(False)

        def on_download_report(self) -> None:
            if self._last_report is None:
                QMessageBox.information(self, "No report", "Run a lookup first.")
                return

            fmt = self.report_format.currentText().lower()
            default_name = f"report.{fmt}"
            filter_map = {
                "json": "JSON Files (*.json)",
                "csv": "CSV Files (*.csv)",
                "pdf": "PDF Files (*.pdf)",
            }
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save report",
                default_name,
                filter_map.get(fmt, "All Files (*)"),
            )
            if not file_path:
                return

            try:
                path = Path(file_path)
                if fmt == "json":
                    export_json_owner(self._last_report, path)
                elif fmt == "csv":
                    export_csv_owner(self._last_report, path)
                elif fmt == "pdf":
                    generate_pdf_owner(self._last_report, path)
                else:
                    raise ValueError(f"Unknown format: {fmt}")
            except Exception as exc:
                QMessageBox.warning(self, "Save failed", f"{type(exc).__name__}: {exc}")
                return

            QMessageBox.information(self, "Report saved", f"Saved to {file_path}")
            self.status.setText("Cancelled.")

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            self._cancel_tasks()
            event.accept()

    app = QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    w = MainWindow(settings)
    w.resize(960, 520)
    w.show()

    with loop:
        loop.run_forever()
