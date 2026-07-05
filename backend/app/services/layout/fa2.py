"""Numeric force solver, ported from vis-network's forceAtlas2Based physics.

Formulas pinned from github.com/visjs/vis-network (master branch, fetched
2026-07-05) — no version is pinned in index.html yet (that lands with the
frontend integration phase), so this is the best available source-of-truth
snapshot; revisit if/when the frontend pins an exact release.

Sources read directly (not just docs):
  - lib/network/modules/components/physics/FA2BasedRepulsionSolver.js
  - lib/network/modules/components/physics/BarnesHutSolver.js (parent class:
    overlapAvoidanceFactor, avoidOverlap clamping)
  - lib/network/modules/components/physics/CentralGravitySolver.js
  - lib/network/modules/components/physics/SpringSolver.js
  - lib/network/modules/PhysicsEngine.js (_performStep, calculateComponentVelocity)

Repulsion (ForceAtlas2BasedRepulsionSolver._calculateForces):
    degree_i = edge_count_i + 1                          # only the "self" node's
                                                          # own degree, NOT the
                                                          # other node's — this
                                                          # makes the repulsion
                                                          # ASYMMETRIC (force on i
                                                          # from j uses degree_i;
                                                          # force on j from i uses
                                                          # degree_j), confirmed
                                                          # from source, not a
                                                          # simplification.
    overlap_avoidance_factor = 1 - clamp(avoidOverlap, 0, 1)   # (BarnesHutSolver.setOptions)
    if overlap_avoidance_factor < 1 and radius_i:
        distance_eff = max(0.1 + overlap_avoidance_factor * radius_i, distance - radius_i)
    else:
        distance_eff = distance
    gravityForce = G * mass_i * mass_j * degree_i / distance_eff**2
    force_on_i += (pos_j - pos_i) * gravityForce         # G is negative in this
                                                          # app's configs, so this
                                                          # pushes i AWAY from j
    # distance == 0 (coincident nodes): vis nudges with a tiny Alea-seeded jitter
    # (dx only, not dy — an accepted vis quirk). This port uses its own seeded
    # np.random.Generator instead (SPC-00021 R3 determinism requirement), jittering
    # both axes for a better-conditioned nudge; the *mechanism* (seeded, so
    # reruns are bit-identical) matters here, not byte parity with vis's jitter.

This module does exact O(n^2) pairwise repulsion (row-chunked to bound
temporaries), not vis's Barnes-Hut spatial tree approximation — a deliberate
simplification the spec sanctions for the <1500-node regime this ships for;
`repulsion_fn` below is an explicit seam for a future Barnes-Hut/grid solver.

Central gravity (CentralGravitySolver._calculateForces):
    dx, dy = -pos_i                                      # vector from node to origin
    distance = |dx, dy|  (== |pos_i| by construction)
    gravityForce = 0 if distance == 0 else centralGravity / distance
    force_i += (dx, dy) * gravityForce
  Note: since |(dx,dy)| == distance, this force has *constant magnitude*
  centralGravity, always pointing toward the origin — "distance-independent"
  is the literal, verified behavior of vis's ONE shared CentralGravitySolver
  class, used for every solver type (not a barnesHut-specific variant as an
  earlier draft of this port's design assumed before the source was read).

Springs (SpringSolver._calculateSpringForce — this app never uses the
"via" support-node branch for smooth curves, since backend edges always
carry an explicit length, matching the SpringSolver's "edge.options.length
!== undefined" branch):
    dx, dy = pos_1 - pos_2
    distance = max(|dx, dy|, 0.01)
    springForce = k_edge * (restLength_edge - distance) / distance
    force_1 += (dx, dy) * springForce
    force_2 -= (dx, dy) * springForce                    # exact Newton's-third-law
                                                          # pair, unlike repulsion

Integration (PhysicsEngine._performStep / calculateComponentVelocity):
    df = damping * v
    a = (f - df) / mass
    v_new = clamp(v + a * dt, -maxVelocity, maxVelocity)
    pos_new = pos + v_new * dt                           # semi-implicit Euler
  Fixed axes: force = 0, velocity = 0, position unchanged on that axis.

Convergence: max ||v|| (per node, over both axes) < minVelocity, or the
iteration cap is reached.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

REPULSION_BLOCK_SIZE = 512


@dataclass(frozen=True)
class SolverParams:
    """Per-layout physics constants — mirrors graph.js's LAYOUTS registry /
    concept-map.js's physics options (gravitationalConstant, centralGravity,
    springConstant, damping, avoidOverlap, minVelocity, maxVelocity)."""

    gravitational_constant: float
    central_gravity: float
    spring_constant: float
    damping: float
    avoid_overlap: float
    min_velocity: float
    max_velocity: float
    dt: float = 0.5
    max_iterations: int = 300


@dataclass
class SolverStep:
    """One solver iteration's state. Pure arrays — engine.py maps these back
    to node ids and shapes the SSE `frame`/`final` event payloads."""

    iteration: int
    pos: np.ndarray  # (n, 2) float64, a fresh copy — safe for a caller to retain
    max_velocity: float
    converged: bool


def default_repulsion_fn(
    pos: np.ndarray,
    mass: np.ndarray,
    degree: np.ndarray,
    radius: np.ndarray,
    gravitational_constant: float,
    avoid_overlap: float,
    rng: np.random.Generator,
    block_size: int = REPULSION_BLOCK_SIZE,
) -> np.ndarray:
    """Exact O(n^2) pairwise repulsion, row-chunked to bound temporaries.

    An explicit, swappable seam: a future Barnes-Hut/grid approximation for
    the 1500+ node regime is a follow-up spec (SPC-00021 §11) and would only
    need to implement this same signature.

    Args:
        pos: (n, 2) node positions.
        mass: (n,) node masses.
        degree: (n,) node degrees (edge count + 1), used asymmetrically per
            vis's own source (force on i from j scales with degree_i only).
        radius: (n,) estimated node radii for avoidOverlap.
        gravitational_constant: G (typically negative — repulsion).
        avoid_overlap: 0-1, vis's avoidOverlap option.
        rng: seeded generator for coincident-point jitter (determinism).
        block_size: row-chunk size bounding the (block, n) temporary matrices.

    Returns:
        (n, 2) force array.
    """
    n = pos.shape[0]
    forces = np.zeros((n, 2), dtype=np.float64)
    if n <= 1 or gravitational_constant == 0:
        return forces

    overlap_avoidance_factor = 1 - min(1.0, max(0.0, avoid_overlap))
    has_radius = radius > 0

    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        block_pos = pos[start:end]  # (b, 2)
        block_mass = mass[start:end]  # (b,)
        block_degree = degree[start:end]  # (b,)
        block_radius = radius[start:end]  # (b,)
        block_has_radius = has_radius[start:end]

        # diff[bi, j] = pos[j] - block_pos[bi] (vector FROM this node TO other j)
        diff = pos[np.newaxis, :, :] - block_pos[:, np.newaxis, :]  # (b, n, 2)
        dist = np.sqrt((diff**2).sum(axis=-1))  # (b, n)

        # Zero out self-interaction: block row bi corresponds to global node
        # start+bi; mask that column so it contributes no force.
        self_rows = np.arange(start, end)
        dist[np.arange(end - start), self_rows] = np.inf

        zero_mask = dist == 0
        if np.any(zero_mask):
            # Coincident-point nudge: seeded jitter on both axes (see module
            # docstring — vis nudges dx only via its own Alea seed; this port
            # jitters both axes with our own seeded generator instead).
            jitter = 0.1 * rng.random(size=(int(zero_mask.sum()), 2))
            diff[zero_mask] = jitter
            dist[zero_mask] = np.sqrt((jitter**2).sum(axis=-1))

        if overlap_avoidance_factor < 1:
            radius_col = block_radius[:, np.newaxis]  # (b, 1), broadcasts over j
            adjusted = np.maximum(0.1 + overlap_avoidance_factor * radius_col, dist - radius_col)
            dist_eff = np.where(block_has_radius[:, np.newaxis], adjusted, dist)
        else:
            dist_eff = dist

        # gravityForce[bi, j] = G * mass[bi] * mass[j] * degree[bi] / dist_eff^2
        gravity_force = (
            gravitational_constant
            * block_mass[:, np.newaxis]
            * mass[np.newaxis, :]
            * block_degree[:, np.newaxis]
            / dist_eff**2
        )
        # Self-column has dist_eff == inf -> gravity_force == 0 there; safe.
        forces[start:end] = (diff * gravity_force[:, :, np.newaxis]).sum(axis=1)

    return forces


def _central_gravity_forces(pos: np.ndarray, central_gravity: float) -> np.ndarray:
    """Constant-magnitude force toward the origin (see module docstring)."""
    n = pos.shape[0]
    if central_gravity == 0:
        return np.zeros((n, 2), dtype=np.float64)
    dxy = -pos
    distance = np.sqrt((dxy**2).sum(axis=-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        gravity_force = np.where(distance == 0, 0.0, central_gravity / distance)
    return dxy * gravity_force[:, np.newaxis]


def _spring_forces(
    pos: np.ndarray,
    edges_i: np.ndarray,
    edges_j: np.ndarray,
    edge_k: np.ndarray,
    edge_length: np.ndarray,
) -> np.ndarray:
    """Per-edge spring force, Newton's-third-law pair (see module docstring)."""
    n = pos.shape[0]
    forces = np.zeros((n, 2), dtype=np.float64)
    if edges_i.size == 0:
        return forces

    dxy = pos[edges_i] - pos[edges_j]  # (m, 2)
    distance = np.maximum(np.sqrt((dxy**2).sum(axis=-1)), 0.01)
    spring_force = edge_k * (edge_length - distance) / distance  # (m,)
    fxy = dxy * spring_force[:, np.newaxis]  # (m, 2)

    np.add.at(forces, edges_i, fxy)
    np.add.at(forces, edges_j, -fxy)
    return forces


def run(
    pos: np.ndarray,
    mass: np.ndarray,
    degree: np.ndarray,
    radius: np.ndarray,
    fixed_x: np.ndarray,
    fixed_y: np.ndarray,
    edges_i: np.ndarray,
    edges_j: np.ndarray,
    edge_k: np.ndarray,
    edge_length: np.ndarray,
    params: SolverParams,
    rng: np.random.Generator,
    repulsion_fn=default_repulsion_fn,
    cancel=None,
) -> Iterator[SolverStep]:
    """Run the force solver, yielding a SolverStep every iteration.

    Args:
        pos: (n, 2) float64 initial positions (mutated copy is yielded, the
            input array itself is not mutated).
        mass: (n,) node masses.
        degree: (n,) node degrees (edge count + 1) for asymmetric repulsion.
        radius: (n,) estimated node radii for avoidOverlap (0 = no estimate).
        fixed_x: (n,) bool — True pins that node's X (velocity/force zeroed).
        fixed_y: (n,) bool — True pins that node's Y.
        edges_i: (m,) int32 source node index per edge.
        edges_j: (m,) int32 target node index per edge.
        edge_k: (m,) float64 per-edge spring constant.
        edge_length: (m,) float64 per-edge rest length.
        params: solver constants for this layout.
        rng: seeded numpy Generator (determinism — same seed, same run, every time).
        repulsion_fn: swappable repulsion implementation (Barnes-Hut seam).
        cancel: optional threading.Event; solve stops (final SolverStep marked
            not converged) as soon as it's set, checked once per iteration.

    Yields:
        SolverStep once per iteration, ending with a converged=True step (or
        a non-converged step at the iteration cap / on cancellation).
    """
    n = pos.shape[0]
    cur_pos = pos.astype(np.float64, copy=True)
    vel = np.zeros((n, 2), dtype=np.float64)

    for iteration in range(1, params.max_iterations + 1):
        if cancel is not None and cancel.is_set():
            yield SolverStep(
                iteration=iteration, pos=cur_pos.copy(), max_velocity=0.0, converged=False
            )
            return

        forces = repulsion_fn(
            cur_pos, mass, degree, radius, params.gravitational_constant, params.avoid_overlap, rng
        )
        forces += _central_gravity_forces(cur_pos, params.central_gravity)
        forces += _spring_forces(cur_pos, edges_i, edges_j, edge_k, edge_length)

        damping_force = params.damping * vel
        accel = (forces - damping_force) / mass[:, np.newaxis]
        new_vel = vel + accel * params.dt
        new_vel = np.clip(new_vel, -params.max_velocity, params.max_velocity)

        # Fixed axes: force/velocity zeroed, position unchanged on that axis.
        new_vel[:, 0] = np.where(fixed_x, 0.0, new_vel[:, 0])
        new_vel[:, 1] = np.where(fixed_y, 0.0, new_vel[:, 1])

        cur_pos = cur_pos + new_vel * params.dt
        vel = new_vel

        speed = np.sqrt((vel**2).sum(axis=-1))
        max_velocity = float(speed.max()) if n > 0 else 0.0
        converged = max_velocity < params.min_velocity

        yield SolverStep(
            iteration=iteration, pos=cur_pos.copy(), max_velocity=max_velocity, converged=converged
        )

        if converged:
            return


def estimate_node_radius(label_len: int) -> float:
    """Estimate a node's rendered radius from its label length, for
    avoidOverlap — the server can't measure actual rendered box sizes.
    Documented approximation (SPC-00021 §6), not a vis.js formula.
    """
    return min(60.0, max(20.0, 12 + 3.5 * label_len))


def seed_rng(node_ids: list[str], algo_version: str) -> np.random.Generator:
    """Deterministic seed derived from the sorted node-id set + algo version,
    so two runs over the same graph are bit-identical (SPC-00021 R3).

    Python's built-in hash() is randomized per-process (PYTHONHASHSEED) unless
    explicitly seeded, so a stable digest is used instead, not hash().
    """
    key = "\x00".join(sorted(node_ids)) + "\x00" + algo_version
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:4], "big")
    return np.random.default_rng(seed)
