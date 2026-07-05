"""Acceptance (in-process ASGI) + Tier 2 tests for the SPC-00021 layout
endpoints: SSE event contract, plain-GET/stream position parity, the layouts
cache, unknown-word handling, concept phonetic edges + multi-concept merge, and
disconnect-driven cancellation.

Only the Mongo seam is faked (``get_words_collection`` -> ``FakeWordsCollection``);
the full router + TreeBuilder + layout engine run for real behind it.
"""

import asyncio
import json
import time

import httpx
import pytest
from app.database import get_words_collection
from app.main import app
from app.routers import layout
from app.services.layout import LAYOUT_ALGO_VERSION

from .fakes import FakeWordsCollection

LANGUAGES = [
    {"lang_code": "en", "lang": "English"},
    {"lang_code": "enm", "lang": "Middle English"},
    {"lang_code": "ang", "lang": "Old English"},
    {"lang_code": "de", "lang": "German"},
    {"lang_code": "es", "lang": "Spanish"},
]

# A word carrying its full inh chain (Kaikki stores the whole chain on one doc):
# cheese -> chese (Middle English) -> ciese (Old English). 3 nodes, 2 edges.
CHEESE_DOCS = [
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

# Two translation hubs (fire, water) with phonetic data on every translated word,
# so resolve_concept's hub strategy returns them through the fake.
CONCEPT_DOCS = [
    {
        "word": "fire",
        "lang": "English",
        "lang_code": "en",
        "pos": "noun",
        "translations": [{"word": "feuer", "lang": "German"}, {"word": "fuego", "lang": "Spanish"}],
        "phonetic": {"ipa": "/fire/", "dolgo_consonants": "PR", "dolgo_first2": "PR"},
        "senses": [{"glosses": ["fire"]}],
    },
    {
        "word": "feuer",
        "lang": "German",
        "lang_code": "de",
        "pos": "noun",
        "phonetic": {"ipa": "/feuer/", "dolgo_consonants": "PR", "dolgo_first2": "PR"},
        "senses": [{"glosses": ["fire"]}],
    },
    {
        "word": "fuego",
        "lang": "Spanish",
        "lang_code": "es",
        "pos": "noun",
        "phonetic": {"ipa": "/fuego/", "dolgo_consonants": "PK", "dolgo_first2": "PK"},
        "senses": [{"glosses": ["fire"]}],
    },
    {
        "word": "water",
        "lang": "English",
        "lang_code": "en",
        "pos": "noun",
        "translations": [{"word": "wasser", "lang": "German"}],
        "phonetic": {"ipa": "/water/", "dolgo_consonants": "TR", "dolgo_first2": "TR"},
        "senses": [{"glosses": ["water"]}],
    },
    {
        "word": "wasser",
        "lang": "German",
        "lang_code": "de",
        "pos": "noun",
        "phonetic": {"ipa": "/wasser/", "dolgo_consonants": "TR", "dolgo_first2": "TR"},
        "senses": [{"glosses": ["water"]}],
    },
]


def _make_fake(docs=CHEESE_DOCS) -> FakeWordsCollection:
    return FakeWordsCollection(list(docs), languages=LANGUAGES)


@pytest.fixture
async def make_client():
    """Factory: hand it a fake, get an in-process AsyncClient bound to it. One
    override is active at a time (drive one client's requests to completion
    before making another); overrides are cleared and clients closed on teardown.
    """
    clients: list[httpx.AsyncClient] = []

    async def _make(fake: FakeWordsCollection) -> httpx.AsyncClient:
        app.dependency_overrides[get_words_collection] = lambda: fake
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        clients.append(client)
        return client

    try:
        yield _make
    finally:
        for client in clients:
            await client.aclose()
        app.dependency_overrides.clear()


async def _collect_sse(client: httpx.AsyncClient, url: str, *, timeout: float = 15.0) -> list[tuple]:
    """Consume an SSE stream to its natural end, returning [(event, data), ...].

    Reads until the server closes the stream (so the write-through completes),
    guarded by a generous timeout that only trips on a hang — never a poll.
    """
    events: list[tuple] = []

    async def _run() -> None:
        async with client.stream("GET", url) as resp:
            assert resp.status_code == 200, f"unexpected status {resp.status_code}"
            assert resp.headers.get("content-type", "").startswith("text/event-stream")
            event_name = None
            data_lines: list[str] = []
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    event_name = line.removeprefix("event: ")
                elif line.startswith("data: "):
                    data_lines.append(line.removeprefix("data: "))
                elif line == "":  # frame terminator
                    if event_name is not None:
                        events.append((event_name, json.loads("".join(data_lines))))
                    event_name, data_lines = None, []
                # ": ..." comment (heartbeat) lines are ignored

    await asyncio.wait_for(_run(), timeout=timeout)
    return events


# --- etymology stream contract ---------------------------------------------


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_tree_stream_event_order_graph_then_final(make_client):
    client = await make_client(_make_fake())
    events = await _collect_sse(client, "/api/etymology/cheese/tree/layout/stream?types=inh")

    names = [name for name, _ in events]
    assert names[0] == "graph"
    assert names[-1] == "final"
    assert set(names) <= {"graph", "frame", "final"}
    assert names.count("final") == 1


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_tree_stream_graph_event_carries_topology_and_meta(make_client):
    client = await make_client(_make_fake())
    events = await _collect_sse(client, "/api/etymology/cheese/tree/layout/stream?types=inh")

    graph = events[0][1]
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == {"cheese:English", "chese:Middle English", "ciese:Old English"}
    # Additive fields (spec §6): every node carries family + tier.
    assert all("family" in n and "tier" in n for n in graph["nodes"])
    meta = graph["meta"]
    assert meta["layout"] == "force-directed"
    assert meta["algo_version"] == LAYOUT_ALGO_VERSION
    assert meta["node_count"] == 3
    assert meta["cache"] == "miss"


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_tree_stream_final_positions_match_plain_get(make_client):
    """Deterministic layout: an independent stream solve and the plain GET solve
    of the same request produce identical (rounded) positions."""
    client = await make_client(_make_fake())
    params = "types=inh&layout=force-directed"

    get_resp = await client.get(f"/api/etymology/cheese/tree/layout?{params}")
    assert get_resp.status_code == 200
    get_positions = get_resp.json()["positions"]

    # Force the stream to re-solve rather than read the just-written cache.
    client_fake = app.dependency_overrides[get_words_collection]()
    client_fake.database["layouts"]._docs.clear()

    events = await _collect_sse(client, f"/api/etymology/cheese/tree/layout/stream?{params}")
    final = [data for name, data in events if name == "final"][-1]

    assert final["positions"] == get_positions
    assert set(final["positions"]) == {
        "cheese:English",
        "chese:Middle English",
        "ciese:Old English",
    }


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_plain_get_meta_reports_solve_stats_and_cache_miss(make_client):
    client = await make_client(_make_fake())
    resp = await client.get("/api/etymology/cheese/tree/layout?types=inh")
    body = resp.json()
    assert resp.status_code == 200
    assert body["meta"]["cache"] == "miss"
    assert body["meta"]["algo_version"] == LAYOUT_ALGO_VERSION
    assert "solve_ms" in body["meta"]
    assert set(body["positions"]) == {n["id"] for n in body["nodes"]}


# --- cache behaviour --------------------------------------------------------


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_second_plain_get_is_cache_hit(make_client):
    client = await make_client(_make_fake())
    url = "/api/etymology/cheese/tree/layout?types=inh"
    first = (await client.get(url)).json()
    second = (await client.get(url)).json()
    assert first["meta"]["cache"] == "miss"
    assert second["meta"]["cache"] == "hit"
    assert first["positions"] == second["positions"]


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_stream_after_get_is_cache_hit_with_zero_frames(make_client):
    client = await make_client(_make_fake())
    params = "types=inh"
    await client.get(f"/api/etymology/cheese/tree/layout?{params}")  # warm the cache

    events = await _collect_sse(client, f"/api/etymology/cheese/tree/layout/stream?{params}")
    names = [name for name, _ in events]
    assert names == ["graph", "final"]  # no frames on a hit
    assert events[0][1]["meta"]["cache"] == "hit"


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_stream_write_through_populates_cache(make_client):
    """The stream's own write-through must populate the cache (its own put_cached
    path, distinct from the plain GET's): a following GET must report a hit."""
    client = await make_client(_make_fake())
    params = "types=inh"
    # Consume the whole stream (miss) — _collect_sse reads to end so write-through runs.
    await _collect_sse(client, f"/api/etymology/cheese/tree/layout/stream?{params}")

    body = (await client.get(f"/api/etymology/cheese/tree/layout?{params}")).json()
    assert body["meta"]["cache"] == "hit"


# --- error / edge scenarios -------------------------------------------------


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_unknown_word_streams_single_orphan_not_500(make_client):
    client = await make_client(FakeWordsCollection([], languages=LANGUAGES))
    events = await _collect_sse(client, "/api/etymology/zzzzz/tree/layout/stream?types=inh")

    names = [name for name, _ in events]
    assert names[0] == "graph"
    assert names[-1] == "final"
    graph = events[0][1]
    assert [n["id"] for n in graph["nodes"]] == ["zzzzz:English"]
    assert "zzzzz:English" in events[-1][1]["positions"]


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_invalid_layout_rejected(make_client):
    client = await make_client(_make_fake())
    resp = await client.get("/api/etymology/cheese/tree/layout?layout=spiral")
    assert resp.status_code == 400


# --- concept map layout -----------------------------------------------------


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_concept_stream_populates_phonetic_edges_without_worker(make_client):
    client = await make_client(FakeWordsCollection(list(CONCEPT_DOCS), languages=LANGUAGES))
    events = await _collect_sse(client, "/api/concept-map/layout/stream?concepts=fire")

    graph = events[0][1]
    assert graph["meta"]["layout"] == "concept"
    assert {w["id"] for w in graph["words"]} == {"fire:English", "feuer:German", "fuego:Spanish"}
    # Server computes phonetic edges (the client Worker does this in client mode).
    assert len(graph["phonetic_edges"]) >= 1
    assert all({"source", "target", "similarity"} <= e.keys() for e in graph["phonetic_edges"])

    final = events[-1][1]
    assert set(final["positions"]) == {"fire:English", "feuer:German", "fuego:Spanish"}


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_concept_layout_merges_multiple_concepts(make_client):
    client = await make_client(FakeWordsCollection(list(CONCEPT_DOCS), languages=LANGUAGES))
    body = (await client.get("/api/concept-map/layout?concepts=fire,water")).json()
    # fire {fire, feuer, fuego} + water {water, wasser}, deduped by id -> 5 nodes.
    assert {w["id"] for w in body["words"]} == {
        "fire:English",
        "feuer:German",
        "fuego:Spanish",
        "water:English",
        "wasser:German",
    }
    assert set(body["positions"]) == {w["id"] for w in body["words"]}


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_concept_layout_is_order_invariant(make_client):
    """The solved layout must not depend on concept order (the cache key sorts
    the concept list, so an order-dependent layout would poison the shared
    cache slot). Each request re-solves fresh (cache cleared between)."""
    fake = FakeWordsCollection(list(CONCEPT_DOCS), languages=LANGUAGES)
    client = await make_client(fake)

    forward = (await client.get("/api/concept-map/layout?concepts=fire,water")).json()["positions"]
    fake.database["layouts"]._docs.clear()  # force a fresh solve, not a cache hit
    reverse = (await client.get("/api/concept-map/layout?concepts=water,fire")).json()["positions"]

    assert forward == reverse


@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_concept_unknown_returns_404(make_client):
    client = await make_client(FakeWordsCollection([], languages=LANGUAGES))
    resp = await client.get("/api/concept-map/layout?concepts=nonesuch")
    assert resp.status_code == 404


# --- disconnect -> cancellation (Tier 2, drives the generator directly) ------


def _stub_job() -> "layout._SolveJob":
    return layout._SolveJob(
        layout="force-directed",
        graph={"nodes": [], "edges": []},
        node_ids=["a:English"],
        edge_count=0,
        solve_kwargs={"layout": "force-directed", "nodes": [], "edges": []},
        cache_params={"kind": "etymology", "word": "a", "algo_version": LAYOUT_ALGO_VERSION},
        graph_hash="test-hash",
    )


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_stream_generator_close_runs_cancel_finally():
    """Closing the SSE generator (e.g. Starlette aborting it on disconnect) runs
    the `finally` that sets the solver's cancellation Event."""

    class _StubRequest:
        async def is_disconnected(self) -> bool:
            return False

    db = FakeWordsCollection([]).database
    agen = layout._stream(_stub_job(), db, _StubRequest()).body_iterator

    first = await agen.__anext__()  # `graph`; generator suspends before solving
    assert first.startswith("event: graph")

    await agen.aclose()
    assert layout.LAST_STREAM_CANCEL["event"].is_set()


@pytest.mark.tier2
@pytest.mark.asyncio
async def test_stream_disconnect_poll_cancels_running_solve(monkeypatch):
    """The disconnect-poll path itself (not just the close `finally`): while a
    solve is running and no frames are arriving, the read loop must poll
    `request.is_disconnected()` and cancel on a positive result."""
    poll_calls = {"n": 0}

    class _DisconnectingRequest:
        async def is_disconnected(self) -> bool:
            poll_calls["n"] += 1
            return True

    def blocking_solve(*_args, cancel=None, **_kwargs):
        # Yield nothing and block until cancelled, so the read loop's queue stays
        # empty and it is forced into the timeout -> is_disconnected() branch.
        while cancel is not None and not cancel.is_set():
            time.sleep(0.005)
        return
        yield  # unreachable, but makes this a generator function

    monkeypatch.setattr(layout.engine, "solve", blocking_solve)
    monkeypatch.setattr(layout, "_DISCONNECT_POLL_S", 0.02)

    db = FakeWordsCollection([]).database
    agen = layout._stream(_stub_job(), db, _DisconnectingRequest()).body_iterator

    first = await agen.__anext__()  # `graph`
    assert first.startswith("event: graph")
    cancel = layout.LAST_STREAM_CANCEL["event"]

    # Next pull enters the read loop, times out with an empty queue, polls
    # is_disconnected() -> True, cancels, and ends the stream with no `final`.
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(agen.__anext__(), timeout=5.0)

    assert poll_calls["n"] >= 1  # the poll path actually ran
    assert cancel.is_set()
