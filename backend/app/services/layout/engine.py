"""Orchestration: wires seed.py/families.py/edge_params.py/fa2.py together
into one `solve()` entry point per layout, yielding a FrameState per solver
iteration (shaped to match the future SSE `frame`/`final` event payloads).

Node/edge input contract (this is new code with no existing callers, so the
shape is chosen fresh rather than mirrored 1:1 from any one JS file):
    nodes: [{"id": str, "label": str, "language": str, "level": int | None}]
        `level` is required for "force-directed"/"era-layered" (etymology
        layouts) and omitted/None for "concept".
    edges: [{"from": str, "to": str, "label": str}]
        For "concept", label is "phonetic" or the etymology relationship name
        (see edge_params.build_concept_edges); `similarity`/`turchin_match`/
        `relationship` fields ride along as extra keys read by that function.

Per-layout behavior, ported from graph.js's LAYOUTS registry / updateGraph
(force-directed, era-layered) and concept-map.js's updateConceptMap:

- Root selection: etymology layouts use the min-level node (graph.js
  findRootAndWordNodes); concept uses the highest-(etymology-edge-)degree
  node, first-encountered on ties (concept-map.js's own centerId pick).
- Seeding: force-directed/concept both seed via seed.compute_tree_positions
  then scale (x0.35 force-directed per graph.js:1052-1061, x0.30 concept per
  concept-map.js's own updateConceptMap — concept seeds from etymology edges
  ONLY, matching the JS's initial paint which runs before the phonetic-edge
  Worker responds). era-layered seeds directly from family-cluster X +
  era-tier Y (graph.js's era-layered buildVisNodes sets x/y directly, no
  separate tree-seed-then-scale step).
- Mass: force-directed root=4, others max(1, 4/2^|level|); era-layered and
  concept both use the vis.js node-option default of 1 for every node (graph.js
  sets mass:1 explicitly for era-layered; concept-map.js never sets a mass
  option at all, so vis's default of 1 applies).
- Fixed axes: force-directed pins the root at (0,0) (fixed x and y), all
  other nodes free; era-layered fixes Y (every node, per its own era tier)
  and leaves X free; concept fixes nothing.
- Degree (for repulsion AND avoidOverlap): counts ALL physics edges,
  including era-layered's invisible intra-family springs (they're still
  edges in the same DataSet in vis.js, so they count toward node.edges.length).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from app.services.layout import fa2
from app.services.layout.edge_params import build_concept_edges, build_vis_edges
from app.services.layout.fa2 import SolverParams
from app.services.layout.families import (
    ERA_TIERS,
    assign_family_cluster_positions,
    build_extra_edges,
    get_era_tier,
    group_nodes_by_tier_and_family,
)
from app.services.layout.seed import compute_tree_positions

LAYOUTS = ("force-directed", "era-layered", "concept")

# Physics constants per layout, from graph.js's LAYOUTS registry
# (force-directed/era-layered) and concept-map.js's own barnesHut options.
# forceAtlas2Based-style formulas (fa2.py) are used for all three here —
# concept's real client-side solver is barnesHut, but SPC-00021 R3 uses one
# solver implementation server-side; visual equivalence, not solver-identity,
# is the acceptance bar (spec §11 risk 1).
_LAYOUT_PARAMS: dict[str, SolverParams] = {
    "force-directed": SolverParams(
        gravitational_constant=-350,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.5,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=300,
    ),
    "era-layered": SolverParams(
        gravitational_constant=-80,
        central_gravity=0.001,
        spring_constant=0.002,
        damping=0.95,
        avoid_overlap=0.7,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=500,
    ),
    "concept": SolverParams(
        gravitational_constant=-8000,
        central_gravity=0.08,
        spring_constant=0.005,
        damping=0.5,
        avoid_overlap=0.5,
        min_velocity=0.75,
        max_velocity=50,
        max_iterations=300,
    ),
}

_FORCE_DIRECTED_SEED_SCALE = 0.35
_CONCEPT_SEED_SCALE = 0.30


@dataclass
class FrameState:
    """Shaped to match the future SSE `frame`/`final` event payloads."""

    i: int
    t_ms: float
    positions: dict[str, tuple[float, float]]
    converged: bool = False
    iterations: int | None = None
    solve_ms: float | None = None
    algo_version: str = ""


@dataclass
class _PreparedGraph:
    node_ids: list[str]
    seed_positions: dict[str, tuple[float, float]]
    mass: np.ndarray
    degree: np.ndarray
    radius: np.ndarray
    fixed_x: np.ndarray
    fixed_y: np.ndarray
    edges_i: np.ndarray
    edges_j: np.ndarray
    edge_k: np.ndarray
    edge_length: np.ndarray


def _display_label(node: dict) -> str:
    language = node.get("language") or ""
    return f"{node.get('label', '')}\n({language})" if language else node.get("label", "")


def pick_etymology_root(nodes: list[dict]) -> str | None:
    """The etymological root: the min-level node (graph.js findRootAndWordNodes)."""
    if not nodes:
        return None
    root = min(nodes, key=lambda n: n.get("level") if n.get("level") is not None else 0)
    return root["id"]


def pick_concept_root(vis_edges: list[dict]) -> str | None:
    """Highest-degree node among the given (from/to-shaped) vis edges,
    first-encountered on ties (concept-map.js's own centerId pick, run over
    the etymology-derived vis edges only)."""
    degree: dict[str, int] = {}
    for e in vis_edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1
    best_id, best_degree = None, 0
    for node_id, d in degree.items():
        if d > best_degree:
            best_id, best_degree = node_id, d
    return best_id


def _seed_force_directed(
    nodes: list[dict], edges: list[dict], root_id: str | None
) -> dict[str, tuple[float, float]]:
    raw = compute_tree_positions(nodes, edges, root_id)
    return {
        nid: (p["x"] * _FORCE_DIRECTED_SEED_SCALE, p["y"] * _FORCE_DIRECTED_SEED_SCALE)
        for nid, p in raw.items()
    }


def _seed_era_layered(nodes: list[dict]) -> dict[str, tuple[float, float]]:
    tiered = group_nodes_by_tier_and_family(nodes)
    x_positions = assign_family_cluster_positions(tiered)
    result = {}
    for n in nodes:
        tier = get_era_tier(n.get("language"))
        y = ERA_TIERS[tier]["y"]
        x = x_positions.get(n["id"], 0.0)
        result[n["id"]] = (x, y)
    return result


def _seed_concept(
    nodes: list[dict], etymology_vis_edges: list[dict], root_id: str | None
) -> dict[str, tuple[float, float]]:
    """Seed from ONLY the etymology-derived vis edges (from/to shape, already
    run through build_concept_edges), matching concept-map.js's own
    computeTreePositions(visNodes, buildConceptEdges([], allEtymologyEdges), centerId)
    call — the initial paint runs before the phonetic-edge Worker responds."""
    if not etymology_vis_edges or root_id is None:
        return {n["id"]: (0.0, 0.0) for n in nodes}
    raw = compute_tree_positions(nodes, etymology_vis_edges, root_id)
    scaled = {
        nid: (p["x"] * _CONCEPT_SEED_SCALE, p["y"] * _CONCEPT_SEED_SCALE) for nid, p in raw.items()
    }
    for n in nodes:
        scaled.setdefault(n["id"], (0.0, 0.0))
    return scaled


def _mass_for(layout: str, node: dict, root_id: str | None) -> float:
    if layout != "force-directed":
        return 1.0
    if node["id"] == root_id:
        return 4.0
    level = node.get("level") or 0
    return max(1.0, 4.0 / (2 ** abs(level)))


def _fixed_for(layout: str, node: dict, root_id: str | None) -> tuple[bool, bool]:
    if layout == "force-directed":
        is_root = node["id"] == root_id
        return (is_root, is_root)
    if layout == "era-layered":
        return (False, True)
    return (False, False)


def _prepare(
    layout: str,
    nodes: list[dict],
    vis_edges: list[dict],
    seed_positions: dict[str, tuple[float, float]],
    root_id: str | None,
) -> tuple[_PreparedGraph, np.ndarray]:
    node_ids = [n["id"] for n in nodes]
    index_of = {nid: i for i, nid in enumerate(node_ids)}
    n = len(node_ids)

    mass = np.array([_mass_for(layout, node, root_id) for node in nodes], dtype=np.float64)
    fixed = [_fixed_for(layout, node, root_id) for node in nodes]
    fixed_x = np.array([f[0] for f in fixed], dtype=bool)
    fixed_y = np.array([f[1] for f in fixed], dtype=bool)
    radius = np.array([fa2.estimate_node_radius(len(_display_label(node))) for node in nodes])

    degree = np.zeros(n, dtype=np.float64)
    # Edges with no explicit springConstant (era-layered's invisible
    # intra-family springs from build_extra_edges — the JS only sets `length`
    # on those, never `springConstant`) fall back to the layout's own default,
    # matching vis.js's per-edge-override-else-network-default behavior.
    default_spring_constant = _LAYOUT_PARAMS[layout].spring_constant
    edges_i_list, edges_j_list, edge_k_list, edge_length_list = [], [], [], []
    for e in vis_edges:
        i, j = index_of.get(e["from"]), index_of.get(e["to"])
        if i is None or j is None:
            continue
        degree[i] += 1
        degree[j] += 1
        edges_i_list.append(i)
        edges_j_list.append(j)
        edge_k_list.append(e.get("springConstant", default_spring_constant))
        edge_length_list.append(e["length"])
    degree += 1  # vis-network's `node.edges.length + 1`

    seed_pos = np.array([seed_positions.get(nid, (0.0, 0.0)) for nid in node_ids], dtype=np.float64)

    return _PreparedGraph(
        node_ids=node_ids,
        seed_positions=seed_positions,
        mass=mass,
        degree=degree,
        radius=radius,
        fixed_x=fixed_x,
        fixed_y=fixed_y,
        edges_i=np.array(edges_i_list, dtype=np.int32),
        edges_j=np.array(edges_j_list, dtype=np.int32),
        edge_k=np.array(edge_k_list, dtype=np.float64),
        edge_length=np.array(edge_length_list, dtype=np.float64),
    ), seed_pos


def prepare_etymology_graph(
    layout: str, nodes: list[dict], edges: list[dict]
) -> tuple[_PreparedGraph, np.ndarray, str | None]:
    """Build the prepared (arrays-only) graph for force-directed/era-layered."""
    if layout not in ("force-directed", "era-layered"):
        msg = f"prepare_etymology_graph does not handle layout {layout!r}"
        raise ValueError(msg)

    root_id = pick_etymology_root(nodes)
    vis_edges = build_vis_edges(edges)

    if layout == "force-directed":
        seed_positions = _seed_force_directed(nodes, edges, root_id)
        all_vis_edges = vis_edges
    else:
        seed_positions = _seed_era_layered(nodes)
        all_vis_edges = vis_edges + build_extra_edges(nodes)

    prepared, seed_pos = _prepare(layout, nodes, all_vis_edges, seed_positions, root_id)
    return prepared, seed_pos, root_id


def prepare_concept_graph(
    nodes: list[dict],
    phonetic_edges: list[dict],
    etymology_edges: list[dict],
    include_etymology_edges: bool,
) -> tuple[_PreparedGraph, np.ndarray, str | None]:
    """Build the prepared (arrays-only) graph for the concept-map layout."""
    # Seeding uses only the etymology-derived vis edges (from/to shape),
    # matching concept-map.js's own buildConceptEdges([], allEtymologyEdges)
    # call used for its initial computeTreePositions seed.
    seed_vis_edges = build_concept_edges([], etymology_edges, True)
    root_id = pick_concept_root(seed_vis_edges)
    seed_positions = _seed_concept(nodes, seed_vis_edges, root_id)

    vis_edges = build_concept_edges(phonetic_edges, etymology_edges, include_etymology_edges)
    # edge_params' vis_edge dicts use "from"/"to" keys already (matching
    # build_vis_edges), populated from source/target — safe to pass straight
    # through to _prepare's from/to reader.

    prepared, seed_pos = _prepare("concept", nodes, vis_edges, seed_positions, root_id)
    return prepared, seed_pos, root_id


def solve(
    layout: str,
    nodes: list[dict],
    edges: list[dict] | None = None,
    *,
    phonetic_edges: list[dict] | None = None,
    etymology_edges: list[dict] | None = None,
    include_etymology_edges: bool = True,
    algo_version: str = "1",
    cancel=None,
) -> Iterator[FrameState]:
    """Run the full layout pipeline for one graph, yielding a FrameState per
    solver iteration. The last yielded FrameState has converged/iterations/
    solve_ms populated (the "final" shape); every prior one does not (the
    "frame" shape) — callers needing SSE cadence throttling apply it on top
    of this iterator, engine.py itself yields every raw iteration.

    Args:
        layout: "force-directed", "era-layered", or "concept".
        nodes: see module docstring for the node dict shape.
        edges: etymology graph edges (required for force-directed/era-layered;
            ignored for concept — pass etymology_edges/phonetic_edges instead).
        phonetic_edges/etymology_edges/include_etymology_edges: concept-only.
        algo_version: stamped onto every FrameState and used to derive the
            deterministic solver RNG seed alongside the node-id set.
        cancel: optional threading.Event to stop the solve early.
    """
    if layout not in LAYOUTS:
        msg = f"Unknown layout {layout!r}, expected one of {LAYOUTS}"
        raise ValueError(msg)

    if layout == "concept":
        prepared, seed_pos, _root_id = prepare_concept_graph(
            nodes, phonetic_edges or [], etymology_edges or [], include_etymology_edges
        )
    else:
        prepared, seed_pos, _root_id = prepare_etymology_graph(layout, nodes, edges or [])

    params = _LAYOUT_PARAMS[layout]
    rng = fa2.seed_rng(prepared.node_ids, algo_version)

    def positions_of(step: fa2.SolverStep) -> dict[str, tuple[float, float]]:
        return {
            nid: (float(step.pos[i, 0]), float(step.pos[i, 1]))
            for i, nid in enumerate(prepared.node_ids)
        }

    start = time.perf_counter()
    # One-step lookahead: only the *truly last* step yielded by fa2.run() (the
    # converged/cancelled/cap-exhausted one) gets the "final" shape; every
    # step before it is a plain "frame". A plain for-loop can't know a step is
    # last until the generator is exhausted, hence buffering one step behind.
    pending = None
    for step in fa2.run(
        seed_pos,
        prepared.mass,
        prepared.degree,
        prepared.radius,
        prepared.fixed_x,
        prepared.fixed_y,
        prepared.edges_i,
        prepared.edges_j,
        prepared.edge_k,
        prepared.edge_length,
        params,
        rng,
        cancel=cancel,
    ):
        if pending is not None:
            t_ms = (time.perf_counter() - start) * 1000
            yield FrameState(
                i=pending.iteration,
                t_ms=t_ms,
                positions=positions_of(pending),
                algo_version=algo_version,
            )
        pending = step

    if pending is not None:
        solve_ms = (time.perf_counter() - start) * 1000
        yield FrameState(
            i=pending.iteration,
            t_ms=solve_ms,
            positions=positions_of(pending),
            converged=pending.converged,
            iterations=pending.iteration,
            solve_ms=solve_ms,
            algo_version=algo_version,
        )
