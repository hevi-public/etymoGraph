"""Tests for TreeBuilder service."""

import pytest
from app.services import lang_cache
from app.services.tree_builder import MAX_DESCENDANTS_PER_NODE, TreeBuilder

from .fakes import FakeWordsCollection


def _seed_lang_codes():
    """Populate lang_cache with the code<->name pairs these tests reference.

    TreeBuilder assumes the cache is already loaded (the router calls
    lang_cache.ensure_loaded before constructing it) — the conftest autouse
    fixture clears it between tests, so each test that needs translation
    seeds it directly rather than exercising the DB-backed ensure_loaded path.
    """
    for code, name in [
        ("en", "English"),
        ("enm", "Middle English"),
        ("ang", "Old English"),
        ("de", "German"),
        ("la", "Latin"),
    ]:
        lang_cache._code_to_name[code] = name
        lang_cache._name_to_code[name] = code


# --- expand_word ---


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_expand_word_creates_root_node_and_traces_ancestry():
    """expand_word adds the root node and walks inh/bor/der ancestry upward.

    Kaikki stores the *entire* ancestor chain on one document's
    etymology_templates (not just the immediate parent) — see CLAUDE.md's
    Kaikki Data Notes — so both ancestor hops live on the "cheese" doc itself.
    """
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "cheese",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [
                    {"name": "inh", "args": {"1": "en", "2": "enm", "3": "chese"}},
                    {"name": "inh", "args": {"1": "enm", "2": "ang", "3": "ciese"}},
                ],
                "etymology_text": "From Middle English chese, from Old English ciese.",
            }
        ]
    )
    builder = TreeBuilder(col, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)

    await builder.expand_word("cheese", "English", base_level=0)

    result = builder.result()
    node_ids = {n["id"] for n in result["nodes"]}
    assert node_ids == {"cheese:English", "chese:Middle English", "ciese:Old English"}
    assert builder.nodes["cheese:English"]["level"] == 0
    assert builder.nodes["chese:Middle English"]["level"] == -1
    assert builder.nodes["ciese:Old English"]["level"] == -2
    assert {"from": "chese:Middle English", "to": "cheese:English", "label": "inh"} in result[
        "edges"
    ]
    assert {"from": "ciese:Old English", "to": "chese:Middle English", "label": "inh"} in result[
        "edges"
    ]


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_expand_word_mention_fallback_when_no_ancestry():
    """With no inh/bor/der templates, expand_word falls back to af/m/m+/l mentions."""
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "chuckle",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [{"name": "m", "args": {"1": "en", "2": "chuck"}}],
                "etymology_text": "Perhaps from chuck.",
            },
            {
                "word": "chuck",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [],
                "etymology_text": "",
            },
        ]
    )
    builder = TreeBuilder(col, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)

    await builder.expand_word("chuckle", "English", base_level=0)

    result = builder.result()
    assert "chuck:English" in builder.nodes
    assert {"from": "chuck:English", "to": "chuckle:English", "label": "mention"} in result["edges"]


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_expand_word_unknown_word_yields_single_orphan_node():
    """Searching a word absent from the DB is a first-class case, not an error:
    it still yields exactly one node and no edges."""
    col = FakeWordsCollection([])
    builder = TreeBuilder(col, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)

    await builder.expand_word("doesnotexist", "English", base_level=0)

    result = builder.result()
    assert result["nodes"] == [
        {
            "id": "doesnotexist:English",
            "label": "doesnotexist",
            "language": "English",
            "level": 0,
            "uncertainty": None,
        }
    ]
    assert result["edges"] == []


# --- find_descendants ---


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_find_descendants_finds_immediate_children():
    """A doc whose ancestry points at the search word becomes a descendant edge."""
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "stemmer",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [
                    {"name": "der", "args": {"1": "en", "2": "en", "3": "stem"}}
                ],
            }
        ]
    )
    builder = TreeBuilder(col, {"der"}, max_ancestor_depth=10, max_descendant_depth=2)

    await builder.find_descendants("stem", "English", "en", parent_level=0)

    result = builder.result()
    assert "stemmer:English" in builder.nodes
    assert builder.nodes["stemmer:English"]["level"] == 1
    assert {"from": "stemmer:English", "to": "stem:English", "label": "der"} in result["edges"]


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_find_descendants_only_includes_immediate_parent():
    """A doc matching the $elemMatch positionally, but whose *first* ancestry
    entry points elsewhere, is not the search word's immediate child."""
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "notachild",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [
                    # First ancestry entry (checked by the immediate-parent guard)
                    # points to a different word than the one we're searching.
                    {"name": "inh", "args": {"1": "en", "2": "ine", "3": "protoword"}},
                    {"name": "der", "args": {"1": "en", "2": "en", "3": "stem"}},
                ],
            }
        ]
    )
    builder = TreeBuilder(col, {"inh", "der"}, max_ancestor_depth=10, max_descendant_depth=2)

    await builder.find_descendants("stem", "English", "en", parent_level=0)

    assert "notachild:English" not in builder.nodes
    assert builder.result()["edges"] == []


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_find_descendants_respects_depth_cap():
    """max_descendant_depth stops recursion before a grandchild is expanded."""
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "child",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [
                    {"name": "der", "args": {"1": "en", "2": "en", "3": "root"}}
                ],
            },
            {
                "word": "grandchild",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [
                    {"name": "der", "args": {"1": "en", "2": "en", "3": "child"}}
                ],
            },
        ]
    )
    builder = TreeBuilder(col, {"der"}, max_ancestor_depth=10, max_descendant_depth=1)

    await builder.find_descendants("root", "English", "en", parent_level=0)

    assert "child:English" in builder.nodes
    assert "grandchild:English" not in builder.nodes


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_find_descendants_caps_at_fifty_deterministically():
    """R1: over the MAX_DESCENDANTS_PER_NODE cap, the surviving set is the
    alphabetically-first 50 (word, lang, pos, etymology_number), not an
    arbitrary Mongo-returned subset, and repeated runs agree."""
    docs = [
        {
            "word": f"d{i:03d}",
            "lang": "English",
            "lang_code": "en",
            "etymology_templates": [{"name": "der", "args": {"1": "en", "2": "en", "3": "root"}}],
        }
        # Deliberately out of alphabetical order, mirroring an unspecified Mongo
        # return order — the sort must fix this regardless of input order.
        for i in reversed(range(MAX_DESCENDANTS_PER_NODE + 5))
    ]
    col = FakeWordsCollection(docs)
    builder = TreeBuilder(col, {"der"}, max_ancestor_depth=10, max_descendant_depth=1)

    await builder.find_descendants("root", "English", "en", parent_level=0)

    found = {n["label"] for n in builder.result()["nodes"]}
    expected = {f"d{i:03d}" for i in range(MAX_DESCENDANTS_PER_NODE)}
    assert found == expected

    # Determinism: a second, independent run over the same fake agrees exactly.
    col2 = FakeWordsCollection(docs)
    builder2 = TreeBuilder(col2, {"der"}, max_ancestor_depth=10, max_descendant_depth=1)
    await builder2.find_descendants("root", "English", "en", parent_level=0)
    assert {n["label"] for n in builder2.result()["nodes"]} == found


# --- expand_cognates ---


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_expand_cognates_finds_cognates_and_expands_their_ancestry():
    """expand_cognates adds a cog edge/node and (same round) traces the
    cognate's own ancestry via expand_word."""
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "fire",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [{"name": "cog", "args": {"1": "de", "2": "Feuer"}}],
            },
            {
                "word": "Feuer",
                "lang": "German",
                "lang_code": "de",
                "etymology_templates": [
                    {"name": "inh", "args": {"1": "de", "2": "ang", "3": "fyr"}}
                ],
            },
            {
                "word": "fyr",
                "lang": "Old English",
                "lang_code": "ang",
                "etymology_templates": [],
            },
        ]
    )
    builder = TreeBuilder(col, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)
    builder.add_node("fire", "English", 0)

    await builder.expand_cognates(max_rounds=2)

    result = builder.result()
    assert {"from": "fire:English", "to": "Feuer:German", "label": "cog"} in result["edges"]
    # Same round expands Feuer's own ancestry (expand_word runs regardless of
    # round exhaustion — only cognate-of-cognate discovery is round-limited).
    assert "fyr:Old English" in builder.nodes


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_expand_cognates_round_cap_stops_cognate_of_cognate():
    """max_rounds=1 discovers direct cognates but not cognates-of-cognates;
    a larger round budget reaches them."""
    _seed_lang_codes()
    docs = [
        {
            "word": "fire",
            "lang": "English",
            "lang_code": "en",
            "etymology_templates": [{"name": "cog", "args": {"1": "de", "2": "Feuer"}}],
        },
        {
            "word": "Feuer",
            "lang": "German",
            "lang_code": "de",
            # Feuer's own cognate — only reachable in a second round.
            "etymology_templates": [{"name": "cog", "args": {"1": "la", "2": "ignis"}}],
        },
    ]

    col = FakeWordsCollection(docs)
    builder = TreeBuilder(col, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)
    builder.add_node("fire", "English", 0)
    await builder.expand_cognates(max_rounds=1)
    assert "Feuer:German" in builder.nodes
    assert "ignis:Latin" not in builder.nodes

    # A fresh builder with a larger round budget reaches the cognate-of-cognate.
    col2 = FakeWordsCollection(docs)
    builder2 = TreeBuilder(col2, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)
    builder2.add_node("fire", "English", 0)
    await builder2.expand_cognates(max_rounds=2)
    assert "ignis:Latin" in builder2.nodes


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_expand_cognates_deduplicates_repeated_edges():
    """Two templates naming the same cognate must not produce two edges or
    process the target twice."""
    _seed_lang_codes()
    col = FakeWordsCollection(
        [
            {
                "word": "fire",
                "lang": "English",
                "lang_code": "en",
                "etymology_templates": [
                    {"name": "cog", "args": {"1": "de", "2": "Feuer"}},
                    {"name": "cog", "args": {"1": "de", "2": "Feuer"}},
                ],
            },
            {"word": "Feuer", "lang": "German", "lang_code": "de", "etymology_templates": []},
        ]
    )
    builder = TreeBuilder(col, {"inh"}, max_ancestor_depth=10, max_descendant_depth=1)
    builder.add_node("fire", "English", 0)

    await builder.expand_cognates(max_rounds=2)

    result = builder.result()
    cog_edges = [e for e in result["edges"] if e["label"] == "cog"]
    assert cog_edges == [{"from": "fire:English", "to": "Feuer:German", "label": "cog"}]


def test_add_node():
    """Test node addition with deduplication."""
    # This test doesn't require database access
    col = None  # Placeholder
    builder = TreeBuilder(col, {"inh"}, 10, 3)

    # Add a node
    nid1 = builder.add_node("test", "English", 0)
    assert nid1 == "test:English"
    assert len(builder.nodes) == 1
    assert builder.nodes[nid1]["label"] == "test"

    # Add same node again - should not duplicate
    nid2 = builder.add_node("test", "English", 0)
    assert nid2 == nid1
    assert len(builder.nodes) == 1


def test_add_edge():
    """Test edge addition with deduplication."""
    col = None  # Placeholder
    builder = TreeBuilder(col, {"inh"}, 10, 3)

    # Add an edge
    added1 = builder.add_edge("from:lang", "to:lang", "inh")
    assert added1 is True
    assert len(builder.edges) == 1

    # Add same edge again - should not duplicate
    added2 = builder.add_edge("from:lang", "to:lang", "inh")
    assert added2 is False
    assert len(builder.edges) == 1


def test_result():
    """Test result serialization."""
    col = None  # Placeholder
    builder = TreeBuilder(col, {"inh"}, 10, 3)

    builder.add_node("word1", "English", 0)
    builder.add_node("word2", "Old English", -1)
    builder.add_edge("word2:Old English", "word1:English", "inh")

    result = builder.result()
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
