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
from typing import Any

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

logger = logging.getLogger(__name__)


def run_gui(settings: PhoneintSettings) -> None:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMessageBox,
            QPushButton,
            QProgressBar,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
        from qasync import QEventLoop, asyncSlot
    except Exception as exc:  # pragma: no cover (optional dependency)
        raise RuntimeError(
            "GUI dependencies not installed. Install with `pip install 'phoneint[gui]'`."
        ) from exc

    class MainWindow(QWidget):  # type: ignore[misc]
        def __init__(self, settings: PhoneintSettings) -> None:
            super().__init__()
            self._settings = settings
            self._tasks: set[asyncio.Task[tuple[str, list[SearchResult]]]] = set()

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
            self.evidence_list = QListWidget()
            panels.addWidget(self.evidence_list, 1)
            root.addLayout(panels)

            self.setLayout(root)

            self.lookup_btn.clicked.connect(self.on_lookup)
            self.cancel_btn.clicked.connect(self.on_cancel)

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
            self.results_text.append("")
            self.results_text.append(f"Carrier: {enrichment.carrier}")
            self.results_text.append(f"Region: {enrichment.region_name}")
            self.results_text.append(f"Time zones: {', '.join(enrichment.time_zones)}")
            self.results_text.append(f"Type: {enrichment.number_type}")
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
                completed = 0

                async def run_one(adapter: ReputationAdapter) -> tuple[str, list[SearchResult]]:
                    res = await adapter.check(normalized.e164, limit=5)
                    return adapter.name, res

                task_map: dict[asyncio.Task[tuple[str, list[SearchResult]]], str] = {}
                for ad in adapters:
                    t = asyncio.create_task(run_one(ad))
                    self._tasks.add(t)
                    task_map[t] = ad.name

                self.status.setText("Running adapters...")
                try:
                    for fut in asyncio.as_completed(task_map.keys()):
                        name, results = await fut
                        completed += 1
                        self.progress.setValue(completed)
                        self.status.setText(
                            f"Adapter finished: {name} ({completed}/{len(adapters)})"
                        )
                        for r in results:
                            evidence.append(r)
                            self.evidence_list.addItem(f"[{r.source}] {r.title}")
                except asyncio.CancelledError:
                    self.status.setText("Cancelled.")
                    return
                finally:
                    self._tasks.clear()

            # Score once all evidence is in.
            found_in_scam_db = any(r.source == "public_scam_db" for r in evidence)
            domain_signals = infer_domain_signals(evidence)
            voip = enrichment.number_type == "voip"
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

            self._set_busy(False)
            self.status.setText("Done.")

        def on_cancel(self) -> None:
            self._cancel_tasks()
            self._set_busy(False)
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
