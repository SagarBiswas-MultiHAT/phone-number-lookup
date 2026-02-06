# file: phoneint/core/parser.py
"""
Phone number parsing and normalization.

This module provides small wrappers around `phonenumbers` that:
- normalize user input (E.164-like canonicalization),
- parse with an optional default region,
- validate numbers,
- return common canonical formats (E.164, international, national).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import phonenumbers
from phonenumbers import NumberParseException
from phonenumbers.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import PhoneNumberFormat


class MissingCountryError(ValueError):
    """Raised when a number is missing a country code and no default region is provided."""


class InvalidPhoneNumberError(ValueError):
    """Raised when a number parses but is not a valid phone number."""


_NON_DIALABLE = re.compile(r"[^\d+]+")


def sanitize_number(raw: str) -> str:
    """
    Normalize common phone number input into a parse-friendly string.

    - Trims whitespace.
    - Removes common separators (spaces, dashes, parentheses, dots).
    - Converts an international dialing prefix `00` into `+`.

    This function does not validate; it only sanitizes input.
    """

    s = raw.strip()
    if not s:
        return s

    s = _NON_DIALABLE.sub("", s)
    if s.startswith("00"):
        s = f"+{s[2:]}"
    return s


@dataclass(frozen=True, slots=True)
class NormalizedPhoneNumber:
    """Canonical forms for a parsed, validated phone number."""

    raw: str
    sanitized: str
    e164: str
    international: str
    national: str
    region: str | None
    country_code: int


def parse_number(raw: str, *, default_region: str | None = None) -> PhoneNumber:
    """
    Parse and validate a phone number.

    Args:
        raw: User-provided input (can include spaces/dashes, etc).
        default_region: ISO 3166-1 alpha-2 region (e.g., "US") used when `raw`
            does not include a leading `+` country code.

    Returns:
        A `phonenumbers.PhoneNumber` instance.

    Raises:
        MissingCountryError: if `raw` has no leading `+` and no `default_region`.
        NumberParseException: if `phonenumbers` cannot parse the input.
        InvalidPhoneNumberError: if parsed but not a valid number.
    """

    sanitized = sanitize_number(raw)
    if not sanitized:
        raise NumberParseException(NumberParseException.NOT_A_NUMBER, "Empty input")

    if not sanitized.startswith("+") and not default_region:
        raise MissingCountryError(
            "Missing country code. Provide an E.164 number (e.g., +14155552671) "
            "or specify a default region (e.g., US)."
        )

    region = default_region.upper() if default_region else None
    parsed = phonenumbers.parse(sanitized, region)
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError("Invalid phone number.")
    return parsed


def normalize_formats(parsed: PhoneNumber, *, raw: str, sanitized: str) -> NormalizedPhoneNumber:
    """
    Return canonical number formats for an already-parsed number.
    """

    e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    intl = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
    nat = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
    region = phonenumbers.region_code_for_number(parsed)
    cc = parsed.country_code
    if cc is None:
        # Defensive: libphonenumber should always provide this for parsed numbers,
        # but some type stubs mark it optional.
        raise InvalidPhoneNumberError("Parsed phone number is missing a country code.")
    return NormalizedPhoneNumber(
        raw=raw,
        sanitized=sanitized,
        e164=e164,
        international=intl,
        national=nat,
        region=region,
        country_code=int(cc),
    )


def parse_and_normalize(
    raw: str, *, default_region: str | None = None
) -> tuple[PhoneNumber, NormalizedPhoneNumber]:
    """
    Parse, validate, and return the parsed object plus canonical string formats.
    """

    sanitized = sanitize_number(raw)
    parsed = parse_number(raw, default_region=default_region)
    normalized = normalize_formats(parsed, raw=raw, sanitized=sanitized)
    return parsed, normalized
