"""The ``layouts`` cache collection (SPC-00021 §7).

Server-solved layouts are deterministic per request, so a solve is cached under
a canonical request key. Two invalidation mechanisms keep the cache honest
without a TTL (the dataset is static): the ``algo_version`` is folded into the
key, so a solver/seed change orphans every old entry; and a hash of the built
node-id set is stored alongside, so a data reload that changes which nodes a
word expands to self-invalidates on the next read.

The key/hash builders are pure (Tier 0); the read/write helpers touch Motor and
are exercised at the acceptance tier over ``FakeWordsCollection``. Following the
precompute-collection convention, the request path only ever *reads or
write-throughs* here — there is no separate ETL step because a layout is cheap
to recompute on a miss.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "layouts"


def cache_key(params: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of the canonical-JSON request key.

    ``params`` must already carry ``algo_version`` (and every input that changes
    the topology or the layout), so callers get stable, collision-free ``_id``s.
    Keys are sorted and separators fixed so the digest is independent of dict
    construction order.
    """
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def node_ids_hash(node_ids: list[str]) -> str:
    """Return a SHA-256 fingerprint over the *set* of node ids (sorted, so it is
    insensitive to build order). Kept as a building block; the cache validates
    against the fuller :func:`graph_hash` (which also folds in edges)."""
    joined = "\n".join(sorted(node_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def graph_hash(node_ids: list[str], edge_sigs: list[tuple]) -> str:
    """Return a SHA-256 fingerprint over the built graph — its node-id set *and*
    its position-affecting edges.

    This is what invalidates a cached layout on read: a data reload that changes
    the node set (descendants under the cap) OR the edges (etymology topology, or
    the phonetic similarity values a concept solve derives from ``dolgo_*``
    fields) yields a different hash, so stale positions are never served. Both
    lists are canonicalized order-independently, so build order doesn't matter.
    """
    payload = json.dumps(
        {
            "nodes": sorted(node_ids),
            "edges": sorted(json.dumps(list(sig), ensure_ascii=False) for sig in edge_sigs),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_cached(db: Any, key: str, expected_graph_hash: str) -> dict | None:
    """Return the cached layout doc, or ``None`` on a miss or a stale graph.

    A present entry whose stored ``graph_hash`` no longer matches the freshly
    built graph is treated as a miss (and logged) so a data reload can never
    serve positions for a graph that has since changed.
    """
    doc = await db[COLLECTION].find_one({"_id": key})
    if doc is None:
        return None
    if doc.get("graph_hash") != expected_graph_hash:
        logger.info(
            "layout cache stale for %s", key, extra={"event": "layout.cache.stale", "key": key}
        )
        return None
    return doc


async def put_cached(
    db: Any,
    key: str,
    positions: dict[str, list[float]],
    graph_sig: str,
    *,
    solve_ms: float | None,
    iterations: int | None,
    converged: bool,
    algo_version: str,
) -> None:
    """Write-through the solved layout; best-effort.

    A cache write is never allowed to fail a request: any error is logged once
    at WARN and swallowed (the client already has its answer; the next request
    simply recomputes).
    """
    doc = {
        "_id": key,
        "positions": positions,
        "graph_hash": graph_sig,
        "solve_ms": solve_ms,
        "iterations": iterations,
        "converged": converged,
        "algo_version": algo_version,
        "created_at": datetime.now(tz=UTC),
    }
    try:
        await db[COLLECTION].replace_one({"_id": key}, doc, upsert=True)
    except Exception:
        # Cache write is best-effort: log once at WARN and swallow, never raise.
        logger.warning(
            "layout cache write failed for %s",
            key,
            exc_info=True,
            extra={"event": "layout.cache.write_failed", "key": key},
        )
