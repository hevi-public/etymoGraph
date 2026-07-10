#!/usr/bin/env python3
"""Capture layout characterization snapshots for SPC-00021 (spec §9).

Snapshots the settled positions the plain layout endpoints return for a small
curated scenario set, into ``tests/fixtures/layout/final/``. The live suite
(``tests/integration/test_layout_characterization.py``) replays each stored
request and asserts node-id sets exactly, positions to ``atol=0.5 px``, and
``algo_version`` exactly.

Unlike the SPC-00013 Wiktionary collector, these files carry no hand-curated
fields — regeneration simply overwrites them. Regenerate (and commit the diff
deliberately) whenever ``LAYOUT_ALGO_VERSION`` bumps or the Kaikki dataset is
reloaded; remember to update ``EXPECTED_ALGO_VERSION`` in the live suite
alongside an algo bump.

Run against a live ``make run`` stack with loaded data:
    python scripts/capture_layout_snapshots.py
    make capture-layout-snapshots
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "layout" / "final"
SPEC_ID = "SPC-00021"

API_BASE = os.environ.get("ETYMOGRAPH_API", "http://localhost:8000").rstrip("/")

# Kept deliberately small: both etymology layouts on the §10 reference word,
# plus a single- and a multi-concept map (the merge + sort determinism path).
SCENARIOS: list[dict] = [
    {
        "name": "tree-cheese-force-directed",
        "path": "/api/etymology/cheese/tree/layout",
        "params": {"lang": "English", "types": "inh,bor,der", "layout": "force-directed"},
    },
    {
        "name": "tree-cheese-era-layered",
        "path": "/api/etymology/cheese/tree/layout",
        "params": {"lang": "English", "types": "inh,bor,der", "layout": "era-layered"},
    },
    {
        "name": "concept-fire",
        "path": "/api/concept-map/layout",
        "params": {"concepts": "fire"},
    },
    {
        "name": "concept-fire-water",
        "path": "/api/concept-map/layout",
        "params": {"concepts": "fire,water"},
    },
]

# Volatile meta fields (cache hit/miss, wall-clock solve time) are dropped so a
# no-change regeneration produces a byte-identical snapshot body.
_STABLE_META_FIELDS = ("layout", "algo_version", "node_count", "edge_count", "converged")


def _request_path(scenario: dict) -> str:
    """Build the replayable request path (with encoded query) for a scenario."""
    return f"{scenario['path']}?{urllib.parse.urlencode(scenario['params'])}"


def _fetch(request_path: str) -> dict:
    """GET a JSON body from the live API (long timeout: cold solves take seconds)."""
    with urllib.request.urlopen(f"{API_BASE}{request_path}", timeout=180) as resp:
        if resp.status != 200:
            msg = f"{request_path} returned HTTP {resp.status}"
            raise RuntimeError(msg)
        return json.loads(resp.read())


def capture(scenario: dict) -> Path:
    """Capture one scenario's settled layout into its snapshot file.

    Args:
        scenario: One SCENARIOS entry (name + endpoint path + query params).

    Returns:
        The snapshot file path written.
    """
    request_path = _request_path(scenario)
    body = _fetch(request_path)
    meta = body["meta"]
    snapshot = {
        "spec": SPEC_ID,
        "captured_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "request": request_path,
        "algo_version": meta["algo_version"],
        "meta": {k: meta[k] for k in _STABLE_META_FIELDS if k in meta},
        "positions": body["positions"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{scenario['name']}.json"
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    return out_path


def main() -> int:
    """Capture every scenario, printing one summary line per snapshot."""
    try:
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=5) as resp:
            if resp.status != 200:
                msg = f"health check returned HTTP {resp.status}"
                raise RuntimeError(msg)
    except OSError as exc:
        print(f"API not reachable at {API_BASE}: {exc}; start services with `make run`")
        return 1

    for scenario in SCENARIOS:
        out_path = capture(scenario)
        snap = json.loads(out_path.read_text())
        print(
            f"{out_path.relative_to(REPO_ROOT)}: {snap['meta']['node_count']} nodes, "
            f"algo_version={snap['algo_version']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
