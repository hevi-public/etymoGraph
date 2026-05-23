"""Unit tests for lang_cache.code_to_name / name_to_code resolution chain."""

from __future__ import annotations

import pytest
from app.services import lang_cache


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset module-level cache around each test."""
    lang_cache._code_to_name.clear()
    lang_cache._name_to_code.clear()
    yield
    lang_cache._code_to_name.clear()
    lang_cache._name_to_code.clear()


# --- code_to_name ---------------------------------------------------------


def test_dynamic_cache_hit_wins_over_fallback() -> None:
    lang_cache._code_to_name["la-med"] = "Custom Medieval Latin"
    assert lang_cache.code_to_name("la-med") == "Custom Medieval Latin"


def test_extended_code_fallback_resolves_la_med() -> None:
    assert lang_cache.code_to_name("la-med") == "Medieval Latin"


def test_extended_code_fallback_resolves_roa_oit() -> None:
    assert lang_cache.code_to_name("roa-oit") == "Old Italian"


def test_extended_code_fallback_resolves_fa_cls() -> None:
    assert lang_cache.code_to_name("fa-cls") == "Early Classical Persian"


def test_extended_code_fallback_resolves_xno() -> None:
    assert lang_cache.code_to_name("xno") == "Anglo-Norman"


def test_unknown_code_returns_raw_input() -> None:
    assert lang_cache.code_to_name("zz-unknown-12345") == "zz-unknown-12345"


def test_empty_input_returns_empty() -> None:
    assert lang_cache.code_to_name("") == ""


# --- name_to_code ---------------------------------------------------------


def test_dynamic_name_cache_hit() -> None:
    lang_cache._name_to_code["Medieval Latin"] = "la-med-custom"
    assert lang_cache.name_to_code("Medieval Latin") == "la-med-custom"


def test_name_reverse_lookup_through_extended_codes() -> None:
    assert lang_cache.name_to_code("Medieval Latin") == "la-med"


def test_name_reverse_lookup_returns_raw_when_unknown() -> None:
    assert lang_cache.name_to_code("Some Unknown Language") == "Some Unknown Language"


# --- coverage of the codes that Phase 3 found leaking --------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("la-med", "Medieval Latin"),
        ("la-lat", "Late Latin"),
        ("roa-oit", "Old Italian"),
        ("fa-cls", "Early Classical Persian"),
        ("xno", "Anglo-Norman"),
    ],
)
def test_phase3_observed_codes_resolve(code: str, expected: str) -> None:
    """Codes flagged as `lang_cache miss` in SPC-00013 Phase 3 fixtures."""
    assert lang_cache.code_to_name(code) == expected
