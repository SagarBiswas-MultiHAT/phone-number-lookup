from __future__ import annotations

from pathlib import Path
import json

from phoneint.reputation.signals import SIGNAL_NAMES, apply_signal_overrides, load_signal_overrides


def test_load_signal_overrides_missing(tmp_path: Path) -> None:
    overrides = load_signal_overrides(tmp_path / "missing.json")
    assert set(overrides.keys()) == set(SIGNAL_NAMES)
    assert all(not values for values in overrides.values())


def test_load_signal_overrides_from_file(tmp_path: Path) -> None:
    payload = {
        "voip": ["+14155552671"],
        "found_in_classifieds": ["+12025550199"],
        "business_listing": ["+18005550100", "+18005550111"],
    }
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    overrides = load_signal_overrides(path)
    assert overrides["voip"] == frozenset({"+14155552671"})
    assert overrides["found_in_classifieds"] == frozenset({"+12025550199"})
    assert overrides["business_listing"] == frozenset({"+18005550100", "+18005550111"})


def test_apply_signal_overrides_forces_flags() -> None:
    overrides = {
        "voip": frozenset({"+14155552671"}),
        "found_in_classifieds": frozenset({"+14155552671"}),
        "business_listing": frozenset(),
    }
    domain_signals = {"found_in_classifieds": False, "business_listing": False}
    voip, merged, hits = apply_signal_overrides(
        e164="+14155552671",
        number_type="fixed_line",
        domain_signals=domain_signals,
        overrides=overrides,
    )

    assert voip is True
    assert merged["found_in_classifieds"] is True
    assert merged["business_listing"] is False
    assert hits["voip"] is True
    assert hits["found_in_classifieds"] is True
    assert hits["business_listing"] is False
