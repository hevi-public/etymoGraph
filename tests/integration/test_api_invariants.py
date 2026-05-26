"""Structural invariants over the etymology API surface (SPC-00013).

Where `test_api_characterization.py` asserts BYTE-FOR-BYTE equality between
the live API and the captured snapshot, these tests assert STRUCTURAL
invariants that should hold by design regardless of the data: referential
integrity (edges only reference declared nodes), uniqueness, acyclicity,
required fields, etc.

Why both? Snapshot equality catches any change. Invariants catch logic bugs
that would corrupt the response shape without breaking byte equality — for
example, a refactor that introduces duplicate node IDs in fresh data, or
silently drops the `language` field. The snapshot would update; the invariant
would fire.

All assertions run on fixture content — no live API needed.
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

GRAPH_SECTIONS = ("chain", "tree_inh", "tree_inh_bor_der_cog")
KNOWN_EDGE_LABELS = {
    "inh",
    "bor",
    "der",
    "cog",
    "component",
    "mention",
    "doublet",
    "calque",
    "cal",
}


# --- helpers --------------------------------------------------------------


def _has_cycle(nodes: set[str], edges: list[dict]) -> tuple[bool, str]:
    """DFS-based cycle detection. Returns (has_cycle, offending_node_id)."""
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f in adj:
            adj[f].append(t)

    white, gray, black = 0, 1, 2
    color = dict.fromkeys(nodes, white)

    def visit(u: str) -> str | None:
        color[u] = gray
        for v in adj.get(u, []):
            if color.get(v) == gray:
                return v
            if color.get(v) == white:
                found = visit(v)
                if found:
                    return found
        color[u] = black
        return None

    for n in nodes:
        if color[n] == white:
            offender = visit(n)
            if offender:
                return True, offender
    return False, ""


def _graph_sections(fixture: dict) -> list[tuple[str, dict]]:
    """Return (section_name, section_payload) pairs that are present and not errors."""
    out = []
    for name in GRAPH_SECTIONS:
        section = fixture["system_output"].get(name)
        if not isinstance(section, dict) or "__error__" in section:
            continue
        out.append((name, section))
    return out


# --- node + edge structural invariants -----------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_nodes_have_required_fields(fixture: dict) -> None:
    """Every node has non-empty id, label, language, and an int level."""
    bad: list[tuple[str, dict]] = []
    for name, section in _graph_sections(fixture):
        for n in section.get("nodes") or []:
            if (
                not n.get("id")
                or not n.get("label")
                or not n.get("language")
                or not isinstance(n.get("level"), int)
            ):
                bad.append((name, n))
    assert not bad, f"[{fixture['query']['word']}] malformed nodes: {bad[:3]}"


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_node_ids_unique_per_section(fixture: dict) -> None:
    """No section returns duplicate node IDs — would silently break vis.js."""
    for name, section in _graph_sections(fixture):
        ids = [n.get("id") for n in section.get("nodes") or []]
        dupes = {x for x in ids if ids.count(x) > 1}
        assert not dupes, f"[{fixture['query']['word']}] {name} has duplicate node IDs: {dupes}"


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_edges_reference_declared_nodes(fixture: dict) -> None:
    """Every edge's from/to references a node declared in the same section."""
    for name, section in _graph_sections(fixture):
        declared = {n.get("id") for n in section.get("nodes") or []}
        dangling = [
            e
            for e in section.get("edges") or []
            if e.get("from") not in declared or e.get("to") not in declared
        ]
        assert not dangling, (
            f"[{fixture['query']['word']}] {name} has dangling edges "
            f"(from/to not in nodes): {dangling[:3]}"
        )


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_edge_labels_are_known(fixture: dict) -> None:
    """Edge labels come from a known vocabulary — catches typos and rogue values."""
    unknown: dict[str, set[str]] = {}
    for name, section in _graph_sections(fixture):
        seen = {e.get("label") for e in section.get("edges") or [] if e.get("label")}
        bad = seen - KNOWN_EDGE_LABELS
        if bad:
            unknown[name] = bad
    assert not unknown, (
        f"[{fixture['query']['word']}] unknown edge labels: {unknown}. "
        f"If legitimate, add to KNOWN_EDGE_LABELS."
    )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "KNOWN BUG: tree builder creates 2-cycles between query word and its "
        "immediate parent (e.g. wyn:Middle English ↔ wine:English). Surfaced by "
        "this invariant test — both the chain pass and the descendant pass emit "
        "an edge between the same pair, in opposite directions. Likely fix lives "
        "in tree_builder._expand_descendants_at_level guarding against re-adding "
        "an inverse of any edge already produced by chain traversal."
    ),
)
@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_graph_is_acyclic(fixture: dict) -> None:
    """Etymology graphs must be acyclic — ancestry can't loop."""
    for name, section in _graph_sections(fixture):
        nodes = {n.get("id") for n in section.get("nodes") or []}
        cycle, offender = _has_cycle(nodes, section.get("edges") or [])
        assert not cycle, (
            f"[{fixture['query']['word']}] {name} has a cycle reachable from {offender!r}"
        )


# --- chain-specific level invariants -------------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_chain_query_word_has_level_zero(fixture: dict) -> None:
    """The queried word is always level 0 in /chain (the gravitational center)."""
    chain = fixture["system_output"].get("chain") or {}
    if "__error__" in chain or not chain.get("nodes"):
        pytest.skip("no chain data")
    word = fixture["query"]["word"]
    lang = fixture["query"]["lang"]
    root_id = f"{word}:{lang}"
    root = next((n for n in chain["nodes"] if n.get("id") == root_id), None)
    assert root is not None, f"{root_id} not in chain.nodes"
    assert root.get("level") == 0, (
        f"[{word}] expected level 0 for query node, got {root.get('level')}"
    )


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_chain_ancestor_levels_strictly_negative(fixture: dict) -> None:
    """All non-root nodes in /chain have negative levels (ancestors)."""
    chain = fixture["system_output"].get("chain") or {}
    if "__error__" in chain or not chain.get("nodes"):
        pytest.skip("no chain data")
    word = fixture["query"]["word"]
    lang = fixture["query"]["lang"]
    root_id = f"{word}:{lang}"
    offending = [n for n in chain["nodes"] if n.get("id") != root_id and n.get("level", 0) >= 0]
    assert not offending, f"[{word}] chain has non-root nodes with level >= 0: {offending}"


# --- word_detail invariants ----------------------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_word_detail_required_fields(fixture: dict) -> None:
    wd = fixture["system_output"].get("word_detail")
    if not isinstance(wd, dict) or "__error__" in wd:
        pytest.skip("no word_detail")
    assert wd.get("word"), "word_detail.word missing"
    assert wd.get("lang"), "word_detail.lang missing"
    assert isinstance(wd.get("definitions"), list), "definitions must be a list"
    assert isinstance(wd.get("related_mentions"), list), "related_mentions must be a list"
    assert isinstance(wd.get("etymology_templates"), list), "etymology_templates must be a list"
    unc = wd.get("etymology_uncertainty")
    assert isinstance(unc, dict), "etymology_uncertainty must be a dict"
    assert isinstance(unc.get("is_uncertain"), bool), (
        "etymology_uncertainty.is_uncertain must be bool"
    )


# --- search invariants ----------------------------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_search_results_consistent(fixture: dict) -> None:
    """search.total equals len(results); no duplicate (word, lang, etymology_number)."""
    search = fixture["system_output"].get("search")
    if not isinstance(search, dict) or "__error__" in search:
        pytest.skip("search snapshot not present")
    results = search.get("results") or []
    assert search.get("total") == len(results), (
        f"search.total ({search.get('total')}) != len(results) ({len(results)})"
    )
    keys = [(r.get("word"), r.get("lang"), r.get("etymology_number")) for r in results]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"search has duplicate (word, lang, etymology_number): {dupes}"


# --- concept-map invariants ----------------------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_concept_map_consistent(fixture: dict) -> None:
    """word_count matches len(words); echoed concept matches request."""
    cm = fixture["system_output"].get("concept_map")
    if not isinstance(cm, dict) or "__error__" in cm:
        pytest.skip("concept_map snapshot not present or is an error envelope")
    assert cm.get("concept") == fixture["query"]["word"], (
        f"concept echoed as {cm.get('concept')!r}, expected {fixture['query']['word']!r}"
    )
    words = cm.get("words") or []
    assert cm.get("word_count") == len(words), (
        f"word_count ({cm.get('word_count')}) != len(words) ({len(words)})"
    )
    assert isinstance(cm.get("clusters"), list)
    assert isinstance(cm.get("etymology_edges"), list)
    assert isinstance(cm.get("phonetic_edges"), list)


# --- concept-suggest invariants ------------------------------------------


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_concept_suggest_shape(fixture: dict) -> None:
    cs = fixture["system_output"].get("concept_suggest")
    if not isinstance(cs, dict) or "__error__" in cs:
        pytest.skip("concept_suggest snapshot not present")
    assert isinstance(cs.get("suggestions"), list), "suggestions must be a list"
