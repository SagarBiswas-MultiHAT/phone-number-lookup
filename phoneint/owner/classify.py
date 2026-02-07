"""Ownership classification heuristics."""

from __future__ import annotations

from typing import Iterable

from phonenumbers.phonenumber import PhoneNumber

from .interface import OwnerAssociation, OwnerPII, OwnershipType


def classify(
    parsed_number: PhoneNumber,
    associations: Iterable[OwnerAssociation],
    *,
    voip_flag: bool,
    pii: OwnerPII | None,
) -> OwnershipType:
    if pii is not None:
        return pii.owner_category  # type: ignore[return-value]

    if voip_flag:
        return "voip"

    labels = {a.label for a in associations}
    if "business_listing" in labels:
        return "business"
    if "classified_ad" in labels:
        return "individual"

    return "unknown"
