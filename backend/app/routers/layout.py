"""Server-side layout endpoints with SSE streaming (SPC-00021 §7).

Each search issues one request here. The first SSE event carries the full graph
(the same node/edge shape ``/tree`` / ``/concept-map`` return, plus additive
``family``/``tier`` on etymology nodes and populated ``phonetic_edges`` on
concept graphs), then zero-or-more ``frame`` events stream solver positions, and
exactly one terminal ``final`` (also on a cache hit, with no frames). The plain
``.../layout`` GET returns the settled positions in one shot (snapshot / curl /
cache-warming surface).

Topology is built on the event loop via Motor (the same ``build_tree`` /
``resolve_concept_words`` the byte-identical endpoints use, so there is no
topology drift); the numpy solve runs in a thread (``run_in_executor``) and
pushes frames through a small ``asyncio.Queue`` — frames are droppable
(latest-wins under backpressure), ``final`` never is. A client disconnect sets
the solver's cancellation event.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import threading
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorCollection

from app.database import get_words_collection
from app.routers.concept_map import resolve_concept_words
from app.routers.etymology import build_tree
from app.services import layout_cache, sse
from app.services.layout import (
    LAYOUT_ALGO_VERSION,
    build_similarity_edges_vectorized,
    engine,
    get_era_tier,
    get_lang_family,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# SSE cadence (spec §7): aim for ~12 frames per solve, but never faster than one
# frame per 80 ms, so a fast solve still streams a handful of frames and a slow
# one doesn't flood the client.
_FRAME_TARGET = 12
_MIN_FRAME_INTERVAL_MS = 80.0
# Heartbeat + disconnect-poll cadence for the SSE read loop.
_HEARTBEAT_S = 15.0
_DISCONNECT_POLL_S = 1.0
# Positions are rounded to 1 dp on the wire (smaller frames; deterministic
# equality between the streamed `final` and the plain-GET response).
_POSITION_DP = 1

_ETYMOLOGY_LAYOUTS = ("force-directed", "era-layered")
# The similarity floor the concept `graph` event always carries, matching what
# the client Web Worker emits today; the client filters up from here without a
# refetch. The solve itself uses the requested `threshold`.
_CONCEPT_GRAPH_FLOOR = 0.3

# Test seam: the cancellation Event of the most recently opened stream, so an
# acceptance test can assert a client disconnect propagates to the solver. A
# plain dict (not a module global rebind) keeps it lint-clean and mutable.
LAST_STREAM_CANCEL: dict[str, threading.Event] = {}


@dataclass
class _SolveJob:
    """Everything the plain-GET and streaming paths need, built once from a
    request so both share identical topology, cache keys, and solver inputs."""

    layout: str
    graph: dict
    node_ids: list[str]
    edge_count: int
    solve_kwargs: dict
    cache_params: dict
    graph_hash: str


# --- payload shaping -------------------------------------------------------


def _round_positions(positions: dict[str, tuple[float, float]]) -> dict[str, list[float]]:
    """Round a solver position map to the wire form ``{id: [x, y]}`` (1 dp)."""
    return {
        nid: [round(float(x), _POSITION_DP), round(float(y), _POSITION_DP)]
        for nid, (x, y) in positions.items()
    }


def _frame_payload(state: engine.FrameState) -> dict:
    """Shape a mid-solve ``frame`` event payload."""
    return {
        "i": state.i,
        "t_ms": round(state.t_ms, 1),
        "positions": _round_positions(state.positions),
    }


def _final_payload(state: engine.FrameState) -> dict:
    """Shape the terminal ``final`` event payload (frame + solve stats)."""
    return {
        "i": state.i,
        "t_ms": round(state.t_ms, 1),
        "positions": _round_positions(state.positions),
        "converged": state.converged,
        "iterations": state.iterations,
        "solve_ms": round(state.solve_ms, 1) if state.solve_ms is not None else None,
        "algo_version": state.algo_version,
    }


def _meta(
    job: _SolveJob,
    *,
    cache: str,
    solve_ms: float | None = None,
    iterations: int | None = None,
    converged: bool | None = None,
) -> dict:
    """Build the ``meta`` block (graph counts + cache state + optional solve stats)."""
    meta: dict[str, Any] = {
        "layout": job.layout,
        "algo_version": LAYOUT_ALGO_VERSION,
        "node_count": len(job.node_ids),
        "edge_count": job.edge_count,
        "cache": cache,
    }
    if solve_ms is not None:
        meta["solve_ms"] = solve_ms
    if iterations is not None:
        meta["iterations"] = iterations
    if converged is not None:
        meta["converged"] = converged
    return meta


# --- job builders ----------------------------------------------------------


async def _build_etymology_job(
    col: AsyncIOMotorCollection,
    word: str,
    lang: str,
    layout: str,
    max_ancestor_depth: int,
    max_descendant_depth: int,
    types: str,
    etym: int | None,
) -> _SolveJob:
    """Build the tree topology and package it for an etymology layout solve."""
    tree = await build_tree(col, word, lang, max_ancestor_depth, max_descendant_depth, types, etym)
    nodes = tree["nodes"]
    edges = tree["edges"]

    # Additive fields (spec §6): the backend needs family/tier for era-layered
    # anyway; emitting them lets the frontend colour/band without recomputing.
    for node in nodes:
        node["family"] = get_lang_family(node.get("language") or "")
        node["tier"] = get_era_tier(node.get("language"))

    cache_params = {
        "kind": "etymology",
        "word": word,
        "lang": lang,
        "types": ",".join(sorted(t for t in types.split(",") if t)),
        "max_ancestor_depth": max_ancestor_depth,
        "max_descendant_depth": max_descendant_depth,
        "etym": etym,
        "layout": layout,
        "algo_version": LAYOUT_ALGO_VERSION,
    }
    node_ids = [n["id"] for n in nodes]
    # Fingerprint the graph (nodes + edge endpoints) so a data reload that
    # changes topology invalidates the cache. Labels are excluded: per-edge
    # physics depends on degree, not label, so positions don't change with it.
    edge_sigs = [(e["from"], e["to"]) for e in edges]
    return _SolveJob(
        layout=layout,
        graph={"nodes": nodes, "edges": edges},
        node_ids=node_ids,
        edge_count=len(edges),
        solve_kwargs={
            "layout": layout,
            "nodes": nodes,
            "edges": edges,
            "algo_version": LAYOUT_ALGO_VERSION,
        },
        cache_params=cache_params,
        graph_hash=layout_cache.graph_hash(node_ids, edge_sigs),
    )


async def _build_concept_job(
    col: AsyncIOMotorCollection,
    concepts: str,
    pos: str | None,
    threshold: float,
    include_etymology_edges: bool,
) -> _SolveJob:
    """Resolve one-or-more comma-separated concepts, merge them exactly as
    ``app.js`` does (dedupe words by id, dedupe etymology edges by endpoint
    pair), compute phonetic edges server-side, and package for a concept solve."""
    concept_list = [c.strip() for c in concepts.split(",") if c.strip()]

    merged_words: dict[str, dict] = {}
    merged_etym: list[dict] = []
    seen_etym: set[tuple[str, str]] = set()
    resolution_method = ""
    for concept in concept_list:
        resolved = await resolve_concept_words(col, concept, pos, include_etymology_edges)
        if resolved is None:
            continue
        resolution_method = resolution_method or resolved["resolution_method"]
        for word in resolved["words"]:
            merged_words.setdefault(word["id"], word)
        for edge in resolved["etymology_edges"]:
            key = (min(edge["source"], edge["target"]), max(edge["source"], edge["target"]))
            if key not in seen_etym:
                seen_etym.add(key)
                merged_etym.append(edge)

    if not merged_words:
        detail = f"No words with phonetic data found for concept(s) '{concepts}'"
        raise HTTPException(status_code=404, detail=detail)

    # Sort the merged word set (and etymology edges) into a request-order-
    # independent order BEFORE building nodes. The solve is node-order-dependent
    # (seed BFS, root tie-break), while the cache key sorts the concept list —
    # so without this, `concepts=fire,water` and `concepts=water,fire` would
    # collide to one cache slot yet compute different layouts. Sorting makes the
    # layout deterministic regardless of concept order, matching the key.
    words = sorted(merged_words.values(), key=lambda w: w["id"])
    merged_etym.sort(key=lambda e: (e["source"], e["target"], e.get("relationship", "")))

    # Compute a superset at the lower of the display floor and the requested
    # threshold, then slice: the `graph` event carries the floor set (client
    # filters up), the solve uses only edges at/above `threshold`.
    floor = min(_CONCEPT_GRAPH_FLOOR, threshold)
    phonetic_super = build_similarity_edges_vectorized(words, floor)
    phonetic_graph = [
        e for e in phonetic_super if e["similarity"] >= _CONCEPT_GRAPH_FLOOR or e["turchin_match"]
    ]
    phonetic_solve = [
        e for e in phonetic_super if e["similarity"] >= threshold or e["turchin_match"]
    ]

    nodes = [
        {"id": w["id"], "label": w["word"], "language": w["lang"], "level": None} for w in words
    ]
    graph = {
        "concepts": concept_list,
        "resolution_method": resolution_method,
        "words": words,
        "phonetic_edges": phonetic_graph,
        "etymology_edges": merged_etym if include_etymology_edges else [],
        "clusters": _build_concept_clusters(words),
    }
    cache_params = {
        "kind": "concept",
        "concepts": sorted(concept_list),
        "pos": pos,
        "threshold": threshold,
        "include_etymology_edges": include_etymology_edges,
        "algo_version": LAYOUT_ALGO_VERSION,
    }
    node_ids = [n["id"] for n in nodes]
    # Fingerprint the actual solve inputs: phonetic edges carry their similarity
    # (derived from dolgo_* fields, so a phonetic data reload changes it and
    # invalidates the cache) and the etymology edges (when included) their
    # endpoints. Positions depend on these, not on the node set alone.
    edge_sigs: list[tuple] = [
        ("p", e["source"], e["target"], e["similarity"]) for e in phonetic_solve
    ]
    if include_etymology_edges:
        edge_sigs += [("e", e["source"], e["target"]) for e in merged_etym]
    edge_count = len(phonetic_graph) + (len(merged_etym) if include_etymology_edges else 0)
    return _SolveJob(
        layout="concept",
        graph=graph,
        node_ids=node_ids,
        edge_count=edge_count,
        solve_kwargs={
            "layout": "concept",
            "nodes": nodes,
            "phonetic_edges": phonetic_solve,
            "etymology_edges": merged_etym,
            "include_etymology_edges": include_etymology_edges,
            "algo_version": LAYOUT_ALGO_VERSION,
        },
        cache_params=cache_params,
        graph_hash=layout_cache.graph_hash(node_ids, edge_sigs),
    )


def _build_concept_clusters(words: list[dict]) -> list[dict]:
    """Turchin clusters over the merged word set (import kept local to avoid a
    module-level dependency on the concept service from the layout router)."""
    from app.services.phonetic_similarity import build_clusters

    return build_clusters(words)


# --- solving ---------------------------------------------------------------


def _solve_final_sync(solve_kwargs: dict) -> engine.FrameState | None:
    """Run the whole solve in the calling thread, returning the terminal state."""
    final: engine.FrameState | None = None
    for state in engine.solve(**solve_kwargs):
        if state.solve_ms is not None:
            final = state
    return final


async def _serve_plain(job: _SolveJob, db: Any) -> dict:
    """Cache-checked one-shot solve for the plain ``.../layout`` GET."""
    key = layout_cache.cache_key(job.cache_params)

    cached = await layout_cache.get_cached(db, key, job.graph_hash)
    if cached is not None:
        meta = _meta(
            job,
            cache="hit",
            solve_ms=cached.get("solve_ms"),
            iterations=cached.get("iterations"),
            converged=cached.get("converged"),
        )
        return {**job.graph, "positions": cached["positions"], "meta": meta}

    loop = asyncio.get_running_loop()
    final = await loop.run_in_executor(None, _solve_final_sync, job.solve_kwargs)
    positions = _round_positions(final.positions) if final is not None else {}

    solve_ms = round(final.solve_ms, 1) if final and final.solve_ms is not None else None
    iterations = final.iterations if final else 0
    converged = final.converged if final else False
    await layout_cache.put_cached(
        db,
        key,
        positions,
        job.graph_hash,
        solve_ms=solve_ms,
        iterations=iterations,
        converged=converged,
        algo_version=LAYOUT_ALGO_VERSION,
    )
    meta = _meta(job, cache="miss", solve_ms=solve_ms, iterations=iterations, converged=converged)
    return {**job.graph, "positions": positions, "meta": meta}


def _cached_final_payload(cached: dict) -> dict:
    """Shape the terminal ``final`` event from a cached layout doc (zero frames)."""
    return {
        "i": cached.get("iterations"),
        "t_ms": cached.get("solve_ms"),
        "positions": cached["positions"],
        "converged": cached.get("converged", False),
        "iterations": cached.get("iterations"),
        "solve_ms": cached.get("solve_ms"),
        "algo_version": cached.get("algo_version", LAYOUT_ALGO_VERSION),
    }


def _drop_one(queue: asyncio.Queue) -> None:
    """Discard one queued item to make room (used for latest-wins frame drop)."""
    with contextlib.suppress(asyncio.QueueEmpty):
        queue.get_nowait()


def _make_offer(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
    """Return an ``offer(item)`` callable for the solver thread that hands items
    to the loop-thread queue. Frames are droppable under backpressure (latest
    wins); ``final``/``error``/``done`` always make room and are delivered."""

    def place(item: tuple) -> None:
        if item[0] == "frame":
            if queue.full():
                _drop_one(queue)
        else:
            while queue.full():
                _drop_one(queue)
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(item)

    def offer(item: tuple) -> None:
        loop.call_soon_threadsafe(place, item)

    return offer


def _run_solver(job: _SolveJob, cancel: threading.Event, offer) -> None:
    """Iterate the solve in a worker thread, offering throttled ``frame`` events
    then the ``final`` (or an ``error``), always terminated by ``done``."""
    stride = max(1, math.ceil(engine.iteration_budget(job.layout) / _FRAME_TARGET))
    last_emit_ms = -math.inf
    final_state: engine.FrameState | None = None
    try:
        for state in engine.solve(**job.solve_kwargs, cancel=cancel):
            if state.solve_ms is not None:
                final_state = state
            elif state.i % stride == 0 and (state.t_ms - last_emit_ms >= _MIN_FRAME_INTERVAL_MS):
                last_emit_ms = state.t_ms
                offer(("frame", _frame_payload(state)))
        if final_state is not None:
            offer(("final", _final_payload(final_state)))
    except Exception:
        logger.warning(
            "layout solve failed", exc_info=True, extra={"event": "layout.solve.failed"}
        )
        offer(("error", {"message": "layout solve failed"}))
    finally:
        offer(("done", None))


def _stream(job: _SolveJob, db: Any, request: Request) -> StreamingResponse:
    """SSE response: ``graph`` → ``frame*`` → ``final`` (or immediate ``final``
    on a cache hit), with heartbeats, disconnect-driven cancellation, and a
    fire-and-forget write-through of the settled layout."""

    async def event_stream():
        cancel = threading.Event()
        LAST_STREAM_CANCEL["event"] = cancel
        key = layout_cache.cache_key(job.cache_params)
        try:
            cached = await layout_cache.get_cached(db, key, job.graph_hash)
            yield sse.format_event(
                "graph", {**job.graph, "meta": _meta(job, cache="hit" if cached else "miss")}
            )
            if cached is not None:
                yield sse.format_event("final", _cached_final_payload(cached))
                return

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue(maxsize=2)
            offer = _make_offer(loop, queue)
            fut = loop.run_in_executor(None, _run_solver, job, cancel, offer)

            final_stats: dict | None = None
            last_ping = loop.time()
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=_DISCONNECT_POLL_S)
                except TimeoutError:
                    if await request.is_disconnected():
                        cancel.set()
                        break
                    if loop.time() - last_ping >= _HEARTBEAT_S:
                        last_ping = loop.time()
                        yield sse.format_comment("ping")
                    continue

                kind, payload = item
                if kind == "done":
                    break
                if kind == "final":
                    final_stats = payload
                yield sse.format_event(kind, payload)

            await fut
            if final_stats is not None:
                await layout_cache.put_cached(
                    db,
                    key,
                    final_stats["positions"],
                    job.graph_hash,
                    solve_ms=final_stats.get("solve_ms"),
                    iterations=final_stats.get("iterations"),
                    converged=final_stats.get("converged", False),
                    algo_version=LAYOUT_ALGO_VERSION,
                )
        finally:
            cancel.set()

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


def _validate_etymology_layout(layout: str) -> None:
    if layout not in _ETYMOLOGY_LAYOUTS:
        detail = f"layout must be one of {list(_ETYMOLOGY_LAYOUTS)}, got {layout!r}"
        raise HTTPException(status_code=400, detail=detail)


# --- endpoints -------------------------------------------------------------

_TYPES_DESC = "Comma-separated connection types: inh,bor,der,cog"
_LAYOUT_DESC = "force-directed | era-layered"


@router.get("/etymology/{word}/tree/layout")
async def get_tree_layout(
    word: str,
    lang: str = "English",
    max_ancestor_depth: int = 10,
    max_descendant_depth: int = Query(3, ge=1, le=5),
    types: str = Query("inh", description=_TYPES_DESC),
    layout: str = Query("force-directed", description=_LAYOUT_DESC),
    etym: int | None = None,
    col: AsyncIOMotorCollection = Depends(get_words_collection),
) -> dict:
    """Settled etymology layout in one response (snapshot / cache-warming surface)."""
    _validate_etymology_layout(layout)
    job = await _build_etymology_job(
        col, word, lang, layout, max_ancestor_depth, max_descendant_depth, types, etym
    )
    return await _serve_plain(job, col.database)


@router.get("/etymology/{word}/tree/layout/stream")
async def stream_tree_layout(
    request: Request,
    word: str,
    lang: str = "English",
    max_ancestor_depth: int = 10,
    max_descendant_depth: int = Query(3, ge=1, le=5),
    types: str = Query("inh", description=_TYPES_DESC),
    layout: str = Query("force-directed", description=_LAYOUT_DESC),
    etym: int | None = None,
    col: AsyncIOMotorCollection = Depends(get_words_collection),
) -> StreamingResponse:
    """Stream the etymology layout solve over SSE (the UI's single request)."""
    _validate_etymology_layout(layout)
    job = await _build_etymology_job(
        col, word, lang, layout, max_ancestor_depth, max_descendant_depth, types, etym
    )
    return _stream(job, col.database, request)


_CONCEPTS_DESC = "One or more comma-separated concepts (e.g. 'fire,water')"


@router.get("/concept-map/layout")
async def get_concept_layout(
    concepts: str = Query(..., description=_CONCEPTS_DESC),
    pos: str | None = Query(None, description="Part of speech filter"),
    threshold: float = Query(0.3, ge=0, le=1, description="Similarity cutoff for the solve edges"),
    include_etymology_edges: bool = Query(True),
    col: AsyncIOMotorCollection = Depends(get_words_collection),
) -> dict:
    """Settled concept-map layout in one response."""
    job = await _build_concept_job(col, concepts, pos, threshold, include_etymology_edges)
    return await _serve_plain(job, col.database)


@router.get("/concept-map/layout/stream")
async def stream_concept_layout(
    request: Request,
    concepts: str = Query(..., description=_CONCEPTS_DESC),
    pos: str | None = Query(None, description="Part of speech filter"),
    threshold: float = Query(0.3, ge=0, le=1, description="Similarity cutoff for the solve edges"),
    include_etymology_edges: bool = Query(True),
    col: AsyncIOMotorCollection = Depends(get_words_collection),
) -> StreamingResponse:
    """Stream the concept-map layout solve over SSE."""
    job = await _build_concept_job(col, concepts, pos, threshold, include_etymology_edges)
    return _stream(job, col.database, request)
