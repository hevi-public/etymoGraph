"""Golden-fixture parity tests for the language-family / era-tier layout port.

Fixtures were generated from the JS source (frontend/public/js/graph.js) and
live in tests/fixtures/layout/ at the repo root. See families.py for the
functions under test.
"""

import json
from pathlib import Path

import pytest
from app.services.layout.families import (
    DEFAULT_FAMILY_COLOR,
    assign_family_cluster_positions,
    build_extra_edges,
    classify_lang,
    get_era_tier,
    group_nodes_by_tier_and_family,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "layout"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.tier0
def test_classify_lang_matches_golden_fixture():
    """classify_lang(lang) matches the JS-generated golden fixture for every
    real language string in classify-lang.json (the "null" key is verified
    separately since it doesn't represent a literal lookup key)."""
    golden = _load_fixture("classify-lang.json")

    for lang, expected in golden.items():
        if lang == "null":
            continue
        assert classify_lang(lang) == expected, f"mismatch for {lang!r}"


@pytest.mark.tier0
def test_era_tiers_match_golden_fixture():
    """get_era_tier(lang) matches the JS-generated golden fixture. The "null"
    key corresponds to calling get_era_tier(None)."""
    golden = _load_fixture("era-tiers.json")

    for lang, expected_tier in golden.items():
        actual = get_era_tier(None) if lang == "null" else get_era_tier(lang)
        assert actual == expected_tier, f"mismatch for {lang!r}"


@pytest.mark.tier0
def test_era_grouping_matches_golden_fixture():
    """group_nodes_by_tier_and_family, assign_family_cluster_positions, and
    build_extra_edges all match the JS-generated golden fixture for a fixed
    input node list, including dict-ordering and edge-ordering parity."""
    golden = _load_fixture("era-grouping.json")

    nodes = [
        {"id": "a:English", "language": "English"},
        {"id": "b:German", "language": "German"},
        {"id": "c:French", "language": "French"},
        {"id": "d:OldEnglish1", "language": "Old English"},
        {"id": "e:OldEnglish2", "language": "Old English"},
        {"id": "f:Latin", "language": "Latin"},
    ]

    tiered_groups = group_nodes_by_tier_and_family(nodes)
    # JSON always stringifies object keys, so normalize our int keys to str.
    tiered_groups_as_str_keys = {str(tier): families for tier, families in tiered_groups.items()}
    assert tiered_groups_as_str_keys == golden["tieredGroups"]

    cluster_positions = assign_family_cluster_positions(tiered_groups)
    assert cluster_positions == golden["clusterPositions"]

    extra_edges = build_extra_edges(nodes)
    assert extra_edges == golden["extraEdges"]


@pytest.mark.tier0
def test_classify_lang_unknown_language_falls_back_to_other():
    """A language matching no family pattern gets the "other" bucket."""
    assert classify_lang("Klingon") == {
        "family": "other",
        "color": DEFAULT_FAMILY_COLOR,
    }


@pytest.mark.tier0
def test_get_era_tier_falsy_inputs_default_to_tier_six():
    """None and empty string are both "falsy" in the JS `!lang` sense and
    should default to tier 6, same as any unrecognized modern language."""
    assert get_era_tier(None) == 6
    assert get_era_tier("") == 6
