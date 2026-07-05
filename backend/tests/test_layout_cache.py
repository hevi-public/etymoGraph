"""Tier 0 (key/hash canonicalization) + Tier 2 (read/write over the fake) tests
for the layouts cache (SPC-00021 §7)."""

import pytest
from app.services import layout_cache

from .fakes import FakeWordsCollection

# --- Tier 0: canonical key + node-set hash ---


@pytest.mark.tier0
def test_cache_key_is_dict_order_independent():
    a = layout_cache.cache_key({"kind": "etymology", "word": "cheese", "algo_version": "1"})
    b = layout_cache.cache_key({"algo_version": "1", "word": "cheese", "kind": "etymology"})
    assert a == b


@pytest.mark.tier0
def test_cache_key_changes_with_algo_version():
    base = {"kind": "etymology", "word": "cheese"}
    assert layout_cache.cache_key({**base, "algo_version": "1"}) != layout_cache.cache_key(
        {**base, "algo_version": "2"}
    )


@pytest.mark.tier0
def test_cache_key_changes_with_any_param():
    base = {"kind": "etymology", "word": "cheese", "layout": "force-directed", "algo_version": "1"}
    assert layout_cache.cache_key(base) != layout_cache.cache_key(
        {**base, "layout": "era-layered"}
    )


@pytest.mark.tier0
def test_node_ids_hash_is_set_order_independent():
    assert layout_cache.node_ids_hash(["a", "b", "c"]) == layout_cache.node_ids_hash(
        ["c", "a", "b"]
    )


@pytest.mark.tier0
def test_node_ids_hash_changes_with_membership():
    assert layout_cache.node_ids_hash(["a", "b"]) != layout_cache.node_ids_hash(["a", "b", "c"])


# --- Tier 2: write-through then read, over the fake ---


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_put_then_get_roundtrips_the_layout():
    db = FakeWordsCollection([]).database
    node_hash = layout_cache.node_ids_hash(["a:English"])
    await layout_cache.put_cached(
        db,
        "key1",
        {"a:English": [1.0, 2.0]},
        node_hash,
        solve_ms=5.0,
        iterations=10,
        converged=True,
        algo_version="1",
    )
    got = await layout_cache.get_cached(db, "key1", node_hash)
    assert got is not None
    assert got["positions"] == {"a:English": [1.0, 2.0]}
    assert got["converged"] is True
    assert got["iterations"] == 10


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_get_returns_none_when_node_hash_differs():
    """A data reload that changes the node set (different hash) must read as a
    miss, never serve positions for the wrong nodes."""
    db = FakeWordsCollection([]).database
    await layout_cache.put_cached(
        db,
        "key1",
        {"a": [0.0, 0.0]},
        "hash-A",
        solve_ms=1.0,
        iterations=1,
        converged=False,
        algo_version="1",
    )
    assert await layout_cache.get_cached(db, "key1", "hash-B") is None


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_get_missing_key_is_a_miss():
    db = FakeWordsCollection([]).database
    assert await layout_cache.get_cached(db, "absent", "any-hash") is None


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_put_replaces_existing_entry_in_place():
    db = FakeWordsCollection([]).database
    node_hash = layout_cache.node_ids_hash(["a"])
    for solve_ms in (1.0, 2.0):
        await layout_cache.put_cached(
            db,
            "key1",
            {"a": [0.0, 0.0]},
            node_hash,
            solve_ms=solve_ms,
            iterations=1,
            converged=True,
            algo_version="1",
        )
    # A single entry, holding the latest write (upsert-in-place, not duplicated).
    assert await db["layouts"].find_one({"_id": "key1"}) is not None
    got = await layout_cache.get_cached(db, "key1", node_hash)
    assert got["solve_ms"] == 2.0
