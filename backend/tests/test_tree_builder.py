"""Tests for TreeBuilder service."""

import pytest
from app.services.tree_builder import TreeBuilder


@pytest.mark.asyncio
async def test_expand_word_basic():
    """Test basic word expansion with simple ancestry.

    TODO: Implement test once test database fixture is ready.
    This should verify that expand_word correctly:
    - Creates a node for the searched word
    - Traces ancestry upward
    - Adds edges between ancestors
    """


@pytest.mark.asyncio
async def test_find_descendants():
    """Test descendant discovery from an ancestor word.

    TODO: Implement test once test database fixture is ready.
    This should verify that find_descendants correctly:
    - Finds words derived from the ancestor
    - Respects max_descendant_depth
    - Only includes immediate children
    """


@pytest.mark.asyncio
async def test_expand_cognates():
    """Test cognate expansion from existing nodes.

    TODO: Implement test once test database fixture is ready.
    This should verify that expand_cognates correctly:
    - Finds cognates for all nodes
    - Respects max_rounds parameter
    - Avoids duplicate edges
    """


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
