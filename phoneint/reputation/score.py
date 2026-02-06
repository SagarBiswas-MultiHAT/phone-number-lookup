# file: phoneint/reputation/score.py
"""
Explainable risk scoring.

This scoring engine is intentionally transparent: it returns both the numeric
score and a breakdown of which signals contributed what.

Weights are configurable (e.g., via YAML config loaded by `phoneint.config`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from phoneint.reputation.adapter import SearchResult


@dataclass(frozen=True, slots=True)
class ScoreSignal:
    name: str
    weight: float
    value: float
    contribution: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "weight": self.weight,
            "value": self.value,
            "contribution": self.contribution,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RiskScoreResult:
    score: int
    breakdown: list[ScoreSignal]

    def to_dict(self) -> dict[str, object]:
        return {"score": self.score, "breakdown": [b.to_dict() for b in self.breakdown]}


def default_score_weights() -> dict[str, float]:
    """
    Default, conservative weights.

    Positive increases risk; negative reduces risk.
    """

    return {
        "found_in_scam_db": 60.0,
        "voip": 15.0,
        "found_in_classifieds": 15.0,
        "business_listing": -10.0,
        # Contribution = weight_per_year * min(age_years, 10)
        "age_of_first_mention_per_year": -2.0,
    }


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def score_risk(
    *,
    found_in_scam_db: bool,
    voip: bool,
    found_in_classifieds: bool,
    business_listing: bool,
    age_of_first_mention_days: int | None = None,
    weights: Mapping[str, float] | None = None,
) -> RiskScoreResult:
    """
    Compute an explainable risk score.

    Args:
        found_in_scam_db: True if matched a scam list/dataset.
        voip: True if number type appears to be VOIP.
        found_in_classifieds: True if evidence suggests classifieds listings.
        business_listing: True if evidence suggests legitimate business listings.
        age_of_first_mention_days: Optional age estimate; older generally reduces risk.
        weights: Weight overrides.
    """

    w = dict(default_score_weights())
    if weights:
        for k, v in weights.items():
            w[str(k)] = float(v)

    breakdown: list[ScoreSignal] = []

    def add_bool(name: str, value: bool, *, reason: str) -> None:
        weight = float(w.get(name, 0.0))
        v = 1.0 if value else 0.0
        breakdown.append(
            ScoreSignal(name=name, weight=weight, value=v, contribution=weight * v, reason=reason),
        )

    add_bool("found_in_scam_db", found_in_scam_db, reason="Matched a public scam dataset")
    add_bool("voip", voip, reason="libphonenumber classified the number as VOIP")
    add_bool(
        "found_in_classifieds",
        found_in_classifieds,
        reason="Evidence URL matched a classifieds domain heuristic",
    )
    add_bool(
        "business_listing",
        business_listing,
        reason="Evidence URL matched a business listing domain heuristic",
    )

    if age_of_first_mention_days is not None and age_of_first_mention_days >= 0:
        weight = float(w.get("age_of_first_mention_per_year", 0.0))
        age_years = age_of_first_mention_days / 365.0
        capped_years = _clamp(age_years, 0.0, 10.0)
        contribution = weight * capped_years
        breakdown.append(
            ScoreSignal(
                name="age_of_first_mention_per_year",
                weight=weight,
                value=capped_years,
                contribution=contribution,
                reason="Older first-mention generally reduces risk (capped at 10 years)",
            )
        )

    raw_score = sum(b.contribution for b in breakdown)
    score = int(round(_clamp(raw_score, 0.0, 100.0)))
    return RiskScoreResult(score=score, breakdown=breakdown)


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


def infer_domain_signals(results: Sequence[SearchResult]) -> dict[str, bool]:
    """
    Infer coarse signals from result URLs using transparent heuristics.

    These heuristics are intentionally simple and auditable; customize as needed.
    """

    found_in_classifieds = False
    business_listing = False
    for r in results:
        url = (r.url or "").lower()
        if any(m in url for m in _CLASSIFIEDS_MARKERS):
            found_in_classifieds = True
        if any(m in url for m in _BUSINESS_MARKERS):
            business_listing = True
    return {
        "found_in_classifieds": found_in_classifieds,
        "business_listing": business_listing,
    }
