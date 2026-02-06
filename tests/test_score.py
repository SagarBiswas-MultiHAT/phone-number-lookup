# file: tests/test_score.py
from __future__ import annotations

from datetime import datetime, timezone

from phoneint.reputation.adapter import SearchResult
from phoneint.reputation.score import default_score_weights, infer_domain_signals, score_risk


def test_score_risk_breakdown_and_clamp() -> None:
    weights = default_score_weights()
    res = score_risk(
        found_in_scam_db=True,
        voip=True,
        found_in_classifieds=True,
        business_listing=False,
        age_of_first_mention_days=0,
        weights=weights,
    )
    assert 0 <= res.score <= 100
    assert len(res.breakdown) >= 4
    # Scam DB match should be a strong positive contribution.
    scam_items = [b for b in res.breakdown if b.name == "found_in_scam_db"]
    assert scam_items and scam_items[0].contribution > 0


def test_score_weights_override() -> None:
    res = score_risk(
        found_in_scam_db=True,
        voip=False,
        found_in_classifieds=False,
        business_listing=False,
        age_of_first_mention_days=None,
        weights={"found_in_scam_db": 5},
    )
    assert res.score == 5


def test_infer_domain_signals() -> None:
    ts = datetime.now(tz=timezone.utc)
    results = [
        SearchResult(
            title="x",
            url="https://craigslist.org/foo",
            snippet="",
            timestamp=ts,
            source="duckduckgo",
        ),
        SearchResult(
            title="y",
            url="https://www.yelp.com/biz/example",
            snippet="",
            timestamp=ts,
            source="google",
        ),
    ]
    signals = infer_domain_signals(results)
    assert signals["found_in_classifieds"] is True
    assert signals["business_listing"] is True
