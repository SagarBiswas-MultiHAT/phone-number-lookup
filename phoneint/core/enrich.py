# file: phoneint/core/enrich.py
"""
Deterministic phone number enrichment helpers.

All functions in this module are pure and do not perform network I/O. They use
metadata embedded in the `phonenumbers` library (derived from libphonenumber).
"""

from __future__ import annotations

from dataclasses import dataclass

from phonenumbers import carrier, geocoder, timezone
from phonenumbers.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import PhoneNumberType, number_type


def number_type_label(nt: int) -> str:
    """Return a stable, user-friendly label for a libphonenumber NumberType."""

    # phonenumbers exposes PhoneNumberType values as ints (and its stubs reflect this),
    # so we type these mappings as int -> str.
    mapping: dict[int, str] = {
        PhoneNumberType.FIXED_LINE: "fixed_line",
        PhoneNumberType.MOBILE: "mobile",
        PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_line_or_mobile",
        PhoneNumberType.TOLL_FREE: "toll_free",
        PhoneNumberType.PREMIUM_RATE: "premium_rate",
        PhoneNumberType.SHARED_COST: "shared_cost",
        PhoneNumberType.VOIP: "voip",
        PhoneNumberType.PERSONAL_NUMBER: "personal_number",
        PhoneNumberType.PAGER: "pager",
        PhoneNumberType.UAN: "uan",
        PhoneNumberType.VOICEMAIL: "voicemail",
        PhoneNumberType.UNKNOWN: "unknown",
    }
    return mapping.get(nt, "unknown")


def is_voip(parsed: PhoneNumber) -> bool:
    """Return True if the number appears to be a VOIP number per libphonenumber."""

    return number_type(parsed) == PhoneNumberType.VOIP


@dataclass(frozen=True, slots=True)
class Enrichment:
    """
    Deterministic enrichment derived from libphonenumber metadata.

    Notes:
        - `region_name` is a locale-dependent description and may be a country or
          more granular region depending on available metadata.
        - Carrier info can be empty for many numbers; this is normal.
    """

    carrier: str
    region_name: str
    time_zones: list[str]
    number_type: str
    iso_country_code: str | None
    dialing_prefix: int


def enrich_number(parsed: PhoneNumber, *, locale: str = "en") -> Enrichment:
    """
    Enrich a parsed number with deterministic metadata.
    """

    carrier_name = carrier.name_for_number(parsed, locale) or ""
    region_name = geocoder.description_for_number(parsed, locale) or ""
    time_zones = list(timezone.time_zones_for_number(parsed))
    nt = int(number_type(parsed))
    iso = None
    try:
        # libphonenumber returns None if unknown.
        from phonenumbers import region_code_for_number

        iso = region_code_for_number(parsed)
    except Exception:
        iso = None

    if parsed.country_code is None:
        # Defensive: stubs mark it optional, but it should be set for parsed numbers.
        dialing_prefix = 0
    else:
        dialing_prefix = int(parsed.country_code)

    return Enrichment(
        carrier=carrier_name,
        region_name=region_name,
        time_zones=time_zones,
        number_type=number_type_label(nt),
        iso_country_code=iso,
        dialing_prefix=dialing_prefix,
    )
