"""Tests for template_parser.py's ancestry extraction."""

import pytest
from app.services.template_parser import (
    ANCESTRY_TYPE_ALIASES,
    ANCESTRY_TYPES,
    expand_ancestry_types,
    extract_ancestry,
)


@pytest.mark.tier0
def test_extract_ancestry_recognizes_der():
    """Baseline: the canonical `der` template name is recognized."""
    doc = {
        "etymology_templates": [
            {"name": "der", "args": {"1": "en", "2": "la", "3": "testum"}},
        ],
    }

    ancestry = extract_ancestry(doc)

    assert len(ancestry) == 1
    assert ancestry[0]["word"] == "testum"
    assert ancestry[0]["lang_code"] == "la"
    assert ancestry[0]["type"] == "der"


@pytest.mark.tier0
def test_extract_ancestry_recognizes_derived_alias():
    """Regression: Wiktionary editors sometimes spell out `{{derived|...}}`
    instead of the `{{der|...}}` short form. Kaikki preserves the literal
    name, so the extractor must recognize both.
    """
    doc = {
        "etymology_templates": [
            {"name": "derived", "args": {"1": "en", "2": "la", "3": "alchimista"}},
        ],
    }

    ancestry = extract_ancestry(doc)

    assert len(ancestry) == 1
    assert ancestry[0]["word"] == "alchimista"
    assert ancestry[0]["lang_code"] == "la"


@pytest.mark.tier0
def test_extract_ancestry_normalizes_derived_type_to_der():
    """The `type` field must normalize to `der` so edge labels stay within
    the frontend's `inh|bor|der|cog` convention, regardless of which Kaikki
    spelling produced the match.
    """
    doc = {
        "etymology_templates": [
            {"name": "derived", "args": {"1": "en", "2": "la", "3": "alchimista"}},
        ],
    }

    ancestry = extract_ancestry(doc)

    assert ancestry[0]["type"] == "der"


@pytest.mark.tier0
def test_extract_ancestry_chemistry_fixture_chain():
    """Regression for the chemistry fixture (SPC-00013): three `derived`
    templates form a linear ancestor chain that was previously invisible.
    """
    doc = {
        "etymology_templates": [
            {"args": {"1": "en", "2": "ine-pro", "3": "*ǵʰew-"}, "name": "root"},
            {"args": {"1": "en", "2": "chemist", "3": "ry"}, "name": "suf"},
            {"args": {"1": "en", "2": "la", "3": "alchimista"}, "name": "derived"},
            {
                "args": {"1": "en", "2": "ar", "3": "كيمياء", "4": "اَلْكِيمِيَاء"},
                "name": "derived",
            },
            {
                "args": {
                    "1": "en",
                    "2": "grc",
                    "3": "χυμεία",
                    "4": "",
                    "5": "art of alloying metals",
                },
                "name": "derived",
            },
        ],
    }

    ancestry = extract_ancestry(doc)

    assert [a["word"] for a in ancestry] == ["alchimista", "كيمياء", "χυμεία"]
    assert all(a["type"] == "der" for a in ancestry)


@pytest.mark.tier0
def test_extract_ancestry_respects_restricted_allowed_types_with_alias():
    """When callers restrict to a canonical type (e.g. tree building with
    `types=der`), the `derived` alias must still match.
    """
    doc = {
        "etymology_templates": [
            {"name": "derived", "args": {"1": "en", "2": "la", "3": "alchimista"}},
        ],
    }

    ancestry = extract_ancestry(doc, allowed_types={"der"})

    assert len(ancestry) == 1


@pytest.mark.tier0
def test_extract_ancestry_does_not_leak_derived_into_unrelated_types():
    """Restricting to `inh` alone must not accidentally match `derived` —
    the alias only expands when its canonical type (`der`) is requested.
    """
    doc = {
        "etymology_templates": [
            {"name": "derived", "args": {"1": "en", "2": "la", "3": "alchimista"}},
        ],
    }

    ancestry = extract_ancestry(doc, allowed_types={"inh"})

    assert ancestry == []


@pytest.mark.tier0
def test_expand_ancestry_types_adds_derived_when_der_present():
    assert expand_ancestry_types({"der"}) == {"der", "derived"}


@pytest.mark.tier0
def test_expand_ancestry_types_leaves_unrelated_types_untouched():
    assert expand_ancestry_types({"inh", "bor"}) == {"inh", "bor"}


@pytest.mark.tier0
def test_ancestry_type_aliases_map_derived_to_der():
    assert ANCESTRY_TYPE_ALIASES == {"derived": "der"}
    assert "der" in ANCESTRY_TYPES
    assert "derived" not in ANCESTRY_TYPES
