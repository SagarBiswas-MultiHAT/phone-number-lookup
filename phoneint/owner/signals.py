"""Owner-related signal extraction and confidence scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from phonenumbers.phonenumber import PhoneNumber

from .interface import (
    LegalBasis,
    OwnerAdapter,
    OwnerAssociation,
    OwnerAuditRecord,
    OwnerIntelResult,
    OwnerPII,
    OwnershipType,
    now_utc,
)
from phoneint.owner.classify import classify
from phoneint.reputation.adapter import SearchResult

_CLASSIFIEDS_MARKERS = (
    "craigslist.",
    "gumtree.",
    "olx.",
    "kijiji.",
    "marktplaats.",
    "facebook.com/marketplace",
)
_BUSINESS_MARKERS = (
    "yelp.",
    "yellowpages.",
    "bbb.org",
    "google.com/maps",
    "linkedin.com/company",
)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def _label_from_search_result(r: SearchResult) -> str:
    url = (r.url or "").lower()
    if r.source == "public_scam_db" or url.startswith("scamdb://"):
        return "scam_report"
    if any(m in url for m in _BUSINESS_MARKERS):
        return "business_listing"
    if any(m in url for m in _CLASSIFIEDS_MARKERS):
        return "classified_ad"
    return "mention"


def _sanitize_snippet(text: str) -> str:
    return _EMAIL_RE.sub("[REDACTED_EMAIL]", text)


def associations_from_evidence(evidence: Sequence[SearchResult]) -> list[OwnerAssociation]:
    out: list[OwnerAssociation] = []
    for r in evidence:
        out.append(
            OwnerAssociation(
                source=r.source,
                url=r.url,
                snippet=_sanitize_snippet(r.snippet or ""),
                label=_label_from_search_result(r),
                timestamp=r.timestamp,
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class OwnerSignals:
    found_in_scam_db: bool
    business_listing_count: int
    classified_ads_count: int
    scam_report_count: int
    voip: bool
    evidence_count: int
    sources_count: int
    first_seen: str | None
    last_seen: str | None
    pii_present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "found_in_scam_db": self.found_in_scam_db,
            "business_listing_count": self.business_listing_count,
            "classified_ads_count": self.classified_ads_count,
            "scam_report_count": self.scam_report_count,
            "voip": self.voip,
            "evidence_count": self.evidence_count,
            "sources_count": self.sources_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "pii_present": self.pii_present,
        }


def extract_owner_signals(
    *,
    evidence: Sequence[SearchResult],
    associations: Sequence[OwnerAssociation],
    voip_flag: bool,
    pii_present: bool,
) -> OwnerSignals:
    business_listing_count = sum(1 for a in associations if a.label == "business_listing")
    classified_ads_count = sum(1 for a in associations if a.label == "classified_ad")
    scam_report_count = sum(1 for a in associations if a.label == "scam_report")
    sources_count = len({(r.source or "") for r in evidence if (r.source or "")})

    first_seen: str | None = None
    last_seen: str | None = None
    if evidence:
        ts_sorted = sorted((r.timestamp for r in evidence), key=lambda d: d.timestamp())
        first_seen = ts_sorted[0].isoformat()
        last_seen = ts_sorted[-1].isoformat()

    return OwnerSignals(
        found_in_scam_db=scam_report_count > 0,
        business_listing_count=business_listing_count,
        classified_ads_count=classified_ads_count,
        scam_report_count=scam_report_count,
        voip=voip_flag,
        evidence_count=len(evidence),
        sources_count=sources_count,
        first_seen=first_seen,
        last_seen=last_seen,
        pii_present=pii_present,
    )


@dataclass(frozen=True, slots=True)
class ConfidenceSignal:
    signal: str
    weight: float
    value: float
    contribution: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "weight": self.weight,
            "value": self.value,
            "contribution": self.contribution,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    score: int
    breakdown: list[ConfidenceSignal]

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, "breakdown": [b.to_dict() for b in self.breakdown]}


def default_owner_confidence_weights() -> dict[str, float]:
    return {
        "voip": 25.0,
        "business_listing": 15.0,
        "classified_ad": 10.0,
        "scam_report": 5.0,
        "pii_confirmed": 50.0,
        "multiple_sources": 10.0,
        "evidence_any": 5.0,
    }


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def score_owner_confidence(
    ownership_type: OwnershipType,
    signals: OwnerSignals,
    *,
    weights: Mapping[str, float] | None = None,
) -> ConfidenceResult:
    w = dict(default_owner_confidence_weights())
    if weights:
        for k, v in weights.items():
            w[str(k)] = float(v)

    breakdown: list[ConfidenceSignal] = []

    def add(signal: str, value: float, *, reason: str, cap: float | None = None) -> None:
        weight = float(w.get(signal, 0.0))
        v = float(value)
        if cap is not None:
            v = min(v, cap)
        breakdown.append(
            ConfidenceSignal(
                signal=signal,
                weight=weight,
                value=v,
                contribution=weight * v,
                reason=reason,
            )
        )

    if signals.evidence_count > 0:
        add("evidence_any", 1.0, reason="At least one public evidence item was found")
    if signals.sources_count >= 2:
        add("multiple_sources", 1.0, reason="Evidence spans multiple sources")

    if ownership_type == "voip":
        add("voip", 1.0 if signals.voip else 0.0, reason="Number metadata indicates VOIP")
    elif ownership_type == "business":
        add(
            "business_listing",
            float(signals.business_listing_count),
            cap=3.0,
            reason="Business listing domains referenced this number",
        )
    elif ownership_type == "individual":
        add(
            "classified_ad",
            float(signals.classified_ads_count),
            cap=3.0,
            reason="Classified ad domains referenced this number",
        )

    if signals.scam_report_count > 0:
        add(
            "scam_report",
            float(signals.scam_report_count),
            cap=3.0,
            reason="Scam reports mention this number (weak ownership-type signal)",
        )

    if signals.pii_present:
        add(
            "pii_confirmed",
            1.0,
            reason="Official adapter returned confirmed owner identity (PII-capable)",
        )

    raw = sum(b.contribution for b in breakdown)
    score = int(round(_clamp(raw, 0.0, 100.0)))
    return ConfidenceResult(score=score, breakdown=breakdown)


def _caller_default() -> str:
    return "unknown"


class OwnerIntelEngine:
    def __init__(
        self,
        *,
        adapters: Sequence[OwnerAdapter] | None = None,
        weights: Mapping[str, float] | None = None,
    ) -> None:
        self._adapters = list(adapters or [])
        self._weights = dict(weights) if weights is not None else None

    async def build(
        self,
        e164: str,
        *,
        parsed_number: PhoneNumber,
        evidence: Sequence[SearchResult],
        voip_flag: bool,
        allow_pii: bool,
        legal_basis: LegalBasis | None,
        caller: str | None = None,
    ) -> tuple[OwnerIntelResult, list[OwnerAuditRecord]]:
        associations = associations_from_evidence(evidence)

        audit: list[OwnerAuditRecord] = []
        pii: OwnerPII | None = None

        for adapter in self._adapters:
            if adapter.pii_capable and not allow_pii:
                continue

            if adapter.pii_capable:
                if legal_basis is None or legal_basis.get("consent_obtained") is not True:
                    continue

            try:
                res = await adapter.lookup_owner(
                    e164, legal_basis=legal_basis, limit=5, caller=caller or _caller_default()
                )
                associations.extend(res.associations)
                if pii is None and res.pii is not None:
                    pii = res.pii
                if adapter.pii_capable and legal_basis is not None:
                    audit.append(
                        OwnerAuditRecord(
                            adapter=adapter.name,
                            time=now_utc(),
                            legal_basis=legal_basis,
                            caller=caller or _caller_default(),
                            result="pii_returned" if res.pii is not None else "none",
                        )
                    )
            except PermissionError:
                if adapter.pii_capable and legal_basis is not None:
                    audit.append(
                        OwnerAuditRecord(
                            adapter=adapter.name,
                            time=now_utc(),
                            legal_basis=legal_basis,
                            caller=caller or _caller_default(),
                            result="error",
                        )
                    )
                raise
            except Exception:
                if adapter.pii_capable and legal_basis is not None:
                    audit.append(
                        OwnerAuditRecord(
                            adapter=adapter.name,
                            time=now_utc(),
                            legal_basis=legal_basis,
                            caller=caller or _caller_default(),
                            result="error",
                        )
                    )

        pii_allowed = bool(
            allow_pii and (legal_basis is not None) and legal_basis.get("consent_obtained") and pii
        )

        ownership_type = classify(
            parsed_number,
            associations,
            voip_flag=voip_flag,
            pii=pii if pii_allowed else None,
        )

        signals = extract_owner_signals(
            evidence=evidence,
            associations=associations,
            voip_flag=voip_flag,
            pii_present=pii_allowed,
        )
        confidence = score_owner_confidence(ownership_type, signals, weights=self._weights)

        pii_dict: dict[str, Any] | None = None
        if pii_allowed and pii is not None:
            pii_dict = pii.__dict__

        owner_intel = OwnerIntelResult(
            ownership_type=ownership_type,
            associations=associations,
            signals=signals.to_dict(),
            confidence_score=confidence.score,
            confidence_breakdown=[b.to_dict() for b in confidence.breakdown],
            pii_allowed=pii_allowed,
            pii=pii_dict,
        )

        return owner_intel, audit
