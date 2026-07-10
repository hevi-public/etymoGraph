"""Live characterization of the SPC-00021 layout endpoints (opt-in, `live`).

Runs against a real `make run` stack with loaded data; skips (as pass) when the
API is unreachable, via the shared `api_base` fixture. Two layers:

- Invariants that must hold whatever the data — node-id sets consistent across
  endpoints, positions covering the node set, determinism across reruns.
- Snapshot characterization (spec §9): each fixture under
  ``tests/fixtures/layout/final/`` replays its stored request and must match
  node-id sets exactly, positions to ``atol=0.5 px`` (cross-machine float
  tolerance), and ``algo_version`` exactly. Regenerate the snapshots with
  ``make capture-layout-snapshots`` after an algo bump or a data reload.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

# Must match app.services.layout.LAYOUT_ALGO_VERSION; a bump is a deliberate,
# cache-invalidating change and updates this expectation with it. (The live
# suite runs from the repo root where the `app` package isn't importable, so the
# value is pinned here rather than imported.)
EXPECTED_ALGO_VERSION = "3"

# Cross-machine float tolerance for position equality (spec §9).
POSITION_ATOL = 0.5

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "layout" / "final"
SNAPSHOTS = sorted(SNAPSHOT_DIR.glob("*.json"))


def _get_json(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=30) as resp:
        assert resp.status == 200, f"{path} returned {resp.status}"
        return json.loads(resp.read())


@pytest.mark.live
def test_tree_layout_topology_matches_tree_endpoint(api_base):
    """The layout endpoint builds identical topology to byte-identical `/tree`."""
    params = urllib.parse.urlencode({"types": "inh,bor,der", "lang": "English"})
    tree = _get_json(api_base, f"/api/etymology/cheese/tree?{params}")
    layout = _get_json(
        api_base, f"/api/etymology/cheese/tree/layout?{params}&layout=force-directed"
    )

    assert {n["id"] for n in layout["nodes"]} == {n["id"] for n in tree["nodes"]}
    # Every node has a position; positions cover exactly the node set.
    assert set(layout["positions"]) == {n["id"] for n in layout["nodes"]}
    assert layout["meta"]["algo_version"] == EXPECTED_ALGO_VERSION


@pytest.mark.live
def test_tree_layout_is_deterministic(api_base):
    """Same request twice -> the same positions within float tolerance."""
    path = "/api/etymology/cheese/tree/layout?types=inh&layout=force-directed"
    first = _get_json(api_base, path)["positions"]
    second = _get_json(api_base, path)["positions"]

    assert set(first) == set(second)
    for node_id, (x1, y1) in first.items():
        x2, y2 = second[node_id]
        assert abs(x1 - x2) <= POSITION_ATOL, node_id
        assert abs(y1 - y2) <= POSITION_ATOL, node_id


@pytest.mark.live
def test_layout_final_snapshots_exist():
    """Loud guard: an empty parametrize set below would silently skip-as-pass.

    Green must mean "matched", never "no snapshots collected"."""
    assert SNAPSHOTS, (
        f"No layout snapshots under {SNAPSHOT_DIR}; run `make capture-layout-snapshots` "
        "against a loaded stack and commit the result"
    )


@pytest.mark.live
@pytest.mark.parametrize("snapshot_path", SNAPSHOTS, ids=lambda p: p.stem)
def test_layout_final_matches_snapshot(api_base, snapshot_path):
    """Replaying a snapshot's request reproduces its settled layout (spec §9)."""
    snapshot = json.loads(snapshot_path.read_text())
    assert snapshot["algo_version"] == EXPECTED_ALGO_VERSION, (
        f"{snapshot_path.name} was captured under algo_version {snapshot['algo_version']}; "
        "regenerate with `make capture-layout-snapshots`"
    )

    live = _get_json(api_base, snapshot["request"])
    assert live["meta"]["algo_version"] == EXPECTED_ALGO_VERSION

    live_positions = live["positions"]
    snap_positions = snapshot["positions"]
    # Node-id sets exact: a topology change (data reload, tree-builder change)
    # must fail here, not fuzz past the position tolerance below.
    assert set(live_positions) == set(snap_positions)
    for node_id, (snap_x, snap_y) in snap_positions.items():
        live_x, live_y = live_positions[node_id]
        assert abs(live_x - snap_x) <= POSITION_ATOL, node_id
        assert abs(live_y - snap_y) <= POSITION_ATOL, node_id


@pytest.mark.live
def test_concept_layout_populates_phonetic_edges_and_positions(api_base):
    body = _get_json(api_base, "/api/concept-map/layout?concepts=fire")

    assert body["meta"]["layout"] == "concept"
    word_ids = {w["id"] for w in body["words"]}
    assert len(word_ids) >= 2
    # Phonetic edges are computed server-side here (no client Worker).
    assert isinstance(body["phonetic_edges"], list)
    for edge in body["phonetic_edges"]:
        assert edge["source"] in word_ids
        assert edge["target"] in word_ids
    assert set(body["positions"]) == word_ids
