# file: tests/test_parser.py
from __future__ import annotations

import phonenumbers
import pytest
from phonenumbers.phonenumberutil import PhoneNumberFormat

from phoneint.core.parser import (
    InvalidPhoneNumberError,
    MissingCountryError,
    parse_and_normalize,
    parse_number,
    sanitize_number,
)


def test_sanitize_number_converts_00_prefix() -> None:
    assert sanitize_number("0044 20 8366 1177") == "+442083661177"


def test_parse_and_normalize_e164_roundtrip() -> None:
    example = phonenumbers.example_number("US")
    e164 = phonenumbers.format_number(example, PhoneNumberFormat.E164)
    parsed, normalized = parse_and_normalize(e164)
    assert phonenumbers.is_valid_number(parsed)
    assert normalized.e164 == e164
    assert normalized.international.startswith("+1 ")


def test_parse_number_requires_country_or_region() -> None:
    with pytest.raises(MissingCountryError):
        parse_number("6502530000")


def test_parse_number_invalid_raises() -> None:
    with pytest.raises(InvalidPhoneNumberError):
        parse_number("+19999999999")
