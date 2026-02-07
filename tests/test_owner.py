# file: tests/test_owner.py
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import phonenumbers
import pytest

from phoneint.net.http import HttpClientConfig
from phoneint.owner.classify import classify
from phoneint.owner.interface import (
    LegalBasis,
    OwnerAdapter,
    OwnerAdapterResult,
    OwnerAssociation,
    OwnerPII,
)
from phoneint.owner.signals import (
    OwnerIntelEngine,
    associations_from_evidence,
    extract_owner_signals,
    score_owner_confidence,
)
from phoneint.owner.truecaller_adapter import TruecallerAdapter
from phoneint.reputation.adapter import SearchResult


def test_owner_classify_business_from_business_listing_association() -> None:
    parsed = phonenumbers.parse("+16502530000", None)
    ts = datetime.now(tz=timezone.utc)
    associations = [
        OwnerAssociation(
            source="duckduckgo",
            url="https://www.yelp.com/biz/example",
            snippet="Example business listing",
            label="business_listing",
            timestamp=ts,
        )
    ]
    assert classify(parsed, associations, voip_flag=False, pii=None) == "business"


def test_owner_classify_voip_has_priority() -> None:
    parsed = phonenumbers.parse("+16502530000", None)
    ts = datetime.now(tz=timezone.utc)
    associations = [
        OwnerAssociation(
            source="duckduckgo",
            url="https://www.yelp.com/biz/example",
            snippet="Example business listing",
            label="business_listing",
            timestamp=ts,
        )
    ]
    assert classify(parsed, associations, voip_flag=True, pii=None) == "voip"


def test_owner_signals_counts_and_first_last_seen() -> None:
    ts1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    ts2 = datetime(2025, 1, 2, tzinfo=timezone.utc)
    evidence = [
        SearchResult(
            title="biz",
            url="https://www.yelp.com/biz/example",
            snippet="",
            timestamp=ts2,
            source="duckduckgo",
        ),
        SearchResult(
            title="classified",
            url="https://craigslist.org/foo",
            snippet="",
            timestamp=ts1,
            source="duckduckgo",
        ),
        SearchResult(
            title="scamdb",
            url="scamdb://phoneint_sample_dataset/tech-support",
            snippet="",
            timestamp=ts1,
            source="public_scam_db",
        ),
    ]
    associations = associations_from_evidence(evidence)
    signals = extract_owner_signals(
        evidence=evidence,
        associations=associations,
        voip_flag=False,
        pii_present=False,
    )
    assert signals.business_listing_count == 1
    assert signals.classified_ads_count == 1
    assert signals.scam_report_count == 1
    assert signals.found_in_scam_db is True
    assert signals.first_seen == ts1.isoformat()
    assert signals.last_seen == ts2.isoformat()


def test_owner_confidence_breakdown_sums_to_score_when_not_clamped() -> None:
    # Use small weights to avoid hitting the 0..100 clamp.
    weights = {
        "business_listing": 1.0,
        "classified_ad": 1.0,
        "voip": 1.0,
        "scam_report": 1.0,
        "pii_confirmed": 1.0,
        "multiple_sources": 1.0,
        "evidence_any": 1.0,
    }
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    evidence = [
        SearchResult(
            title="biz",
            url="https://www.yelp.com/biz/example",
            snippet="",
            timestamp=ts,
            source="duckduckgo",
        )
    ]
    associations = associations_from_evidence(evidence)
    signals = extract_owner_signals(
        evidence=evidence,
        associations=associations,
        voip_flag=False,
        pii_present=False,
    )
    res = score_owner_confidence("business", signals, weights=weights)
    total = sum(b.contribution for b in res.breakdown)
    assert res.score == int(round(total))


@pytest.mark.asyncio
async def test_truecaller_adapter_requires_consent() -> None:
    async with httpx.AsyncClient() as client:
        adapter = TruecallerAdapter(
            client=client,
            http_config=HttpClientConfig(),
            enabled=True,
            api_key="test",
            rate_limiter=None,
        )
        with pytest.raises(PermissionError):
            await adapter.lookup_owner(
                "+16502530000",
                legal_basis={"purpose": "customer-verification", "consent_obtained": False},
                caller="tester",
            )


class _StubPiiAdapter(OwnerAdapter):
    name = "stub_pii"
    pii_capable = True

    async def lookup_owner(
        self,
        e164: str,
        *,
        legal_basis: LegalBasis | None,
        limit: int = 5,
        caller: str | None = None,
    ) -> OwnerAdapterResult:
        _ = (limit, caller)
        if legal_basis is None or legal_basis.get("consent_obtained") is not True:
            raise PermissionError("consent required")
        ts = datetime.now(tz=timezone.utc)
        return OwnerAdapterResult(
            associations=[
                OwnerAssociation(
                    source=self.name,
                    url="stub://pii",
                    snippet=e164,
                    label="identity_confirmed",
                    timestamp=ts,
                )
            ],
            pii=OwnerPII(name="Jane Doe", source=self.name, owner_category="individual"),
        )


@pytest.mark.asyncio
async def test_owner_engine_creates_audit_record_when_pii_adapter_called() -> None:
    engine = OwnerIntelEngine(adapters=[_StubPiiAdapter()], weights={"pii_confirmed": 1})
    parsed = phonenumbers.parse("+16502530000", None)
    evidence: list[SearchResult] = []
    legal_basis = {"purpose": "customer-verification", "consent_obtained": True}
    owner_intel, audit = await engine.build(
        "+16502530000",
        parsed_number=parsed,
        evidence=evidence,
        voip_flag=False,
        allow_pii=True,
        legal_basis=legal_basis,
        caller="tester",
    )
    d = owner_intel.to_dict()
    assert d["pii_allowed"] is True
    assert "pii" in d
    assert audit and audit[0].result in ("pii_returned", "none", "error")
