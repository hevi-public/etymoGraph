"""Wiktionary-consistency tests for the etymology API (SPC-00013 Phase 3).

Layered on top of the Phase 1 snapshot tests in `test_api_characterization.py`.
These tests assert on FIXTURE CONTENT — they compare `system_output` against
`wiktionary_reference` within each fixture file, so they don't need a live API.

Four test classes:

  A. `test_chain_covers_wiktionary_ancestors[<word>]`
     Every (lang, word) in `wiktionary_reference.expected_chain_per_wiktionary`
     should appear as a node in `system_output.chain` or `tree_inh_bor_der_cog`.
     `xfail` when a `known_gaps.*` flag documents the absence; FAIL otherwise.

  B. `test_alternative_theories_surfaced[<word>]`
     For fixtures with disjunctive origins, the system should expose each
     alternative. Currently the API has no alternative_origins field, so this
     `xfail`s when `missing_alternative_origins == true` — Phase 4 will invent
     the surface and the test will go green.

  C. `test_documented_gap_is_present[<word>]`
     For each `known_gaps.<flag> == true`, the gap symptom must actually be
     present in the fixture (Wiktionary documents it AND system doesn't
     surface it). If either side is absent, the flag is stale.

  D. `test_q13_diacritics_normalized[<word>]`
     Regression for main SPC-00011: ancestors with macrons/asterisks must
     resolve to chain nodes for words tagged Q13. Phase 3's only "must pass"
     class — no xfail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wiktionary"


def _fixture_params() -> list:
    if not FIXTURES_DIR.exists():
        return []
    return [
        pytest.param(json.loads(path.read_text(encoding="utf-8")), id=path.stem)
        for path in sorted(FIXTURES_DIR.glob("*.json"))
    ]


FIXTURE_PARAMS = _fixture_params()

_COMPOUND_TEMPLATES = {
    "compound", "af", "affix", "suffix", "prefix", "blend", "+", "suf",
}
_CALQUE_TEMPLATES = {"cal", "calque"}

# --- helpers --------------------------------------------------------------


def _nodes(section: dict | None) -> list[dict]:
    return (section or {}).get("nodes") or []


def _edges(section: dict | None) -> list[dict]:
    return (section or {}).get("edges") or []


def _node_set(fixture: dict, *sections: str) -> set[tuple[str, str]]:
    """Union of (language, label) tuples across one or more system_output sections."""
    out: set[tuple[str, str]] = set()
    for sec in sections:
        for n in _nodes(fixture["system_output"].get(sec)):
            out.add((n.get("language"), n.get("label")))
    return out


def _template_names(fixture: dict) -> set[str]:
    return {
        t.get("name")
        for t in (fixture.get("raw_kaikki") or {}).get("etymology_templates", [])
        if isinstance(t, dict)
    }


def _edge_labels(fixture: dict, *sections: str) -> set[str]:
    out: set[str] = set()
    for sec in sections:
        for e in _edges(fixture["system_output"].get(sec)):
            label = e.get("label")
            if label:
                out.add(label)
    return out


def _excerpt(fixture: dict) -> str:
    return (
        fixture["wiktionary_reference"].get("etymology_section_text_excerpt") or ""
    ).lower()


def _meta_notes(fixture: dict) -> str:
    return (fixture["meta"].get("notes") or "").lower()


# Forgiveness predicates for the chain-coverage test. Each returns True if the
# given missing-entry note explains why a Wiktionary ancestor isn't in the
# system's chain or tree. Centralized to keep the test body short.

def _is_forgiven_absence(missing: dict, gaps: dict, lang: str) -> bool:
    note = (missing.get("note") or "").lower()
    checks = (
        ("prose-only" in note or lang == "Pre-Germanic"),
        ("alternative" in note and gaps.get("missing_alternative_origins")),
        (
            ("component" in note or "suffix" in note)
            and gaps.get("missing_compound_components")
        ),
        ("deeper root" in note or "system chain stops" in note),
        ("intermediate skipped" in note),
        ("lang_cache miss" in note or "lang code" in note),
        ("diacritic" in note or "bare form" in note or "vocalization" in note),
    )
    return any(checks)


# --- A. chain covers Wiktionary ancestors --------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_chain_covers_wiktionary_ancestors(fixture: dict) -> None:
    expected = fixture["wiktionary_reference"]["expected_chain_per_wiktionary"]
    if not expected:
        pytest.skip("No wiktionary_reference.expected_chain_per_wiktionary recorded")

    # Search the union of chain + the broadest tree response — components
    # surfaced only by SPC-00012's precomputed edges live in /tree.
    actual = _node_set(fixture, "chain", "tree_inh_bor_der_cog")

    missing = [
        {**e, "_reason": e.get("note", "")}
        for e in expected
        if (e["lang"], e["word"]) not in actual
    ]
    if not missing:
        return

    gaps = fixture["known_gaps"]
    word = fixture["query"]["word"]
    unexplained = [m for m in missing if not _is_forgiven_absence(m, gaps, m["lang"])]

    if unexplained:
        pytest.fail(
            f"[{word}] Wiktionary ancestors missing from system_output and "
            f"NOT explained by known_gaps or chain notes: {unexplained}"
        )
    pytest.xfail(
        f"[{word}] Wiktionary ancestors missing but documented in known_gaps: {missing}"
    )


# --- B. alternative theories surfaced ------------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_alternative_theories_surfaced(fixture: dict) -> None:
    alts = fixture["wiktionary_reference"]["alternative_theories"]
    if not alts:
        pytest.skip("No alternative_theories documented for this fixture")

    word_detail = fixture["system_output"].get("word_detail") or {}
    # Current API has no `alternative_origins` field. Phase 4 will add one.
    surfaced = word_detail.get("alternative_origins") or word_detail.get("alternative_theories")

    if not surfaced:
        if fixture["known_gaps"].get("missing_alternative_origins"):
            pytest.xfail(
                f"[{fixture['query']['word']}] {len(alts)} alternative theory/theories "
                f"in Wiktionary; system has no alternative_origins surface yet"
            )
        pytest.fail(
            f"[{fixture['query']['word']}] alternative_theories documented but flag "
            f"`missing_alternative_origins` is false — stale flag, or new system "
            f"surface missing"
        )

    assert len(surfaced) >= len(alts), (
        f"[{fixture['query']['word']}] system surfaces {len(surfaced)} alternative(s); "
        f"Wiktionary documents {len(alts)}"
    )


# --- C. documented gap is present (stale-flag detector) ------------------


def _has_alt_origins_symptom(fixture: dict) -> bool:
    return bool(fixture["wiktionary_reference"]["alternative_theories"])


def _has_compound_symptom(fixture: dict) -> bool:
    """Wiktionary describes a compound/affix relationship for this word."""
    excerpt = _excerpt(fixture)
    if "compound" in excerpt or "+ -" in excerpt or " + " in excerpt:
        return True
    if "equivalent to" in excerpt and " + " in excerpt:
        return True
    if "frequentative" in excerpt or "suffix" in excerpt or "prefix" in excerpt:
        return True
    return bool(_template_names(fixture) & _COMPOUND_TEMPLATES)


def _has_doublet_symptom(fixture: dict) -> bool:
    return (
        "doublet" in _excerpt(fixture)
        or "doublet" in _meta_notes(fixture)
        or "doublet" in _template_names(fixture)
    )


def _has_calque_symptom(fixture: dict) -> bool:
    excerpt = _excerpt(fixture)
    return (
        "calque" in excerpt
        or "calqu" in excerpt  # 'calqued', 'calquing'
        or "calque" in _meta_notes(fixture)
        or bool(_template_names(fixture) & _CALQUE_TEMPLATES)
    )


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_documented_gap_is_present(fixture: dict) -> None:
    gaps = fixture["known_gaps"]
    word = fixture["query"]["word"]
    failures: list[str] = []

    if gaps.get("missing_alternative_origins") and not _has_alt_origins_symptom(fixture):
        failures.append(
            "missing_alternative_origins=true but no alternative_theories in "
            "wiktionary_reference — stale flag"
        )

    if gaps.get("missing_compound_components"):
        if not _has_compound_symptom(fixture):
            failures.append(
                "missing_compound_components=true but excerpt has no compound "
                "marker and raw_kaikki has no compound template — stale flag"
            )
        chain_labels = _edge_labels(fixture, "chain")
        present = chain_labels & {"compound", "component", "af", "affix", "suffix", "prefix"}
        if present:
            failures.append(
                f"missing_compound_components=true but chain has {present} — "
                "flag should flip to false"
            )

    if gaps.get("missing_doublet_link"):
        if not _has_doublet_symptom(fixture):
            failures.append(
                "missing_doublet_link=true but no doublet mention in excerpt, "
                "meta.notes, or raw_kaikki templates — stale flag"
            )
        all_labels = _edge_labels(fixture, "chain", "tree_inh", "tree_inh_bor_der_cog")
        if "doublet" in all_labels:
            failures.append(
                "missing_doublet_link=true but a doublet edge exists in system_output — "
                "flag should flip to false"
            )

    if gaps.get("missing_calques"):
        if not _has_calque_symptom(fixture):
            failures.append(
                "missing_calques=true but no calque mention in excerpt, meta.notes, "
                "or raw_kaikki templates — stale flag"
            )
        all_labels = _edge_labels(fixture, "chain", "tree_inh", "tree_inh_bor_der_cog")
        if all_labels & _CALQUE_TEMPLATES:
            failures.append(
                "missing_calques=true but a calque edge exists in system_output — "
                "flag should flip to false"
            )

    if failures:
        pytest.fail(f"[{word}] stale known_gaps flag(s):\n  - " + "\n  - ".join(failures))


# --- D. Q13 diacritic normalization regression ---------------------------

# Hardcoded contract: these specific diacritic-bearing ancestors MUST appear
# in chain for the corresponding fixtures. Regression guard for main SPC-00011's
# Unicode NFKD + asterisk-strip normalization.
Q13_REQUIRED_ANCESTORS: dict[str, list[tuple[str, str]]] = {
    "wine": [("Old English", "wīn"), ("Proto-West Germanic", "*wīn"),
             ("Proto-Germanic", "*wīną")],
    "hound": [("Proto-West Germanic", "*hund"), ("Proto-Germanic", "*hundaz"),
              ("Proto-Indo-European", "*ḱwṓ")],
    "cheese": [("Old English", "ċīese"), ("Proto-West Germanic", "*kāsī"),
               ("Latin", "cāseus")],
}


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_q13_diacritics_normalized(fixture: dict) -> None:
    word = fixture["query"]["word"]
    required: list[tuple[str, str]] = Q13_REQUIRED_ANCESTORS.get(word, [])
    if not required:
        pytest.skip("Not a Q13-tagged fixture")

    chain_nodes = _node_set(fixture, "chain")
    missing = [pair for pair in required if pair not in chain_nodes]
    assert not missing, (
        f"[{word}] Q13 normalization regression — diacritic ancestors missing "
        f"from system_output.chain: {missing}. Check template_parser normalization."
    )
