# file: tests/test_public.py
from __future__ import annotations

from phoneint.reputation.public import check_scam_list, load_scam_list


def test_public_scam_list_loads_and_matches() -> None:
    entries = load_scam_list()
    assert entries
    hits = check_scam_list("+14155550100", entries, limit=5)
    assert hits
    assert hits[0].source == "public_scam_db"
