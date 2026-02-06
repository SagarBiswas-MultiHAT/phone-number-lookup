# file: tests/test_enrich.py
from __future__ import annotations

import phonenumbers
from phonenumbers.phonenumberutil import PhoneNumberType

from phoneint.core.enrich import enrich_number, is_voip, number_type_label


def test_enrich_number_returns_expected_fields() -> None:
    parsed = phonenumbers.parse("+16502530000", None)  # Google HQ (stable test vector)
    assert phonenumbers.is_valid_number(parsed)

    e = enrich_number(parsed)
    assert isinstance(e.carrier, str)
    assert isinstance(e.region_name, str)
    assert isinstance(e.time_zones, list)
    assert e.iso_country_code == "US"
    assert e.dialing_prefix == 1
    assert e.number_type in {
        "fixed_line",
        "mobile",
        "fixed_line_or_mobile",
        "toll_free",
        "premium_rate",
        "shared_cost",
        "voip",
        "personal_number",
        "pager",
        "uan",
        "voicemail",
        "unknown",
    }


def test_number_type_label_and_is_voip_are_stable() -> None:
    assert number_type_label(PhoneNumberType.MOBILE) == "mobile"
    parsed = phonenumbers.parse("+16502530000", None)
    assert is_voip(parsed) in (True, False)
