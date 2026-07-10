"""Numeric force solver, ported from vis-network's forceAtlas2Based physics.

Formulas pinned from github.com/visjs/vis-network at tag v9.1.9 — the release
the Phase 3+4 frontend integration (SPC-00021, PR #18) pins in index.html
(vis-network@9.1.9/standalone/umd/vis-network.min.js). Until that PR lands,
index.html still loads unpinned latest from unpkg.

Sources read directly (not just docs), all at the v9.1.9 tag:
  - lib/network/modules/components/physics/FA2BasedRepulsionSolver.js
  - lib/network/modules/components/physics/BarnesHutSolver.js (parent class:
    overlapAvoidanceFactor, avoidOverlap clamping)
  - lib/network/modules/components/physics/CentralGravitySolver.js
  - lib/network/modules/components/physics/FA2BasedCentralGravitySolver.js
  - lib/network/modules/components/physics/SpringSolver.js
  - lib/network/modules/PhysicsEngine.js (init solver selection, _performStep,
    calculateComponentVelocity)

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

Repulsion, barnesHut law (BarnesHutSolver._calculateForces, v9.1.9) — the law
the concept map's client solver runs, selected via
SolverParams.repulsion_law="barneshut". Constants calibrated for one law are
dimensionally wrong under the other: concept's G=-8000 under the FA2 1/d law
overpowers its springs ~100x at typical distances and every concept solve
expands to a velocity-clamp-limited square (the SPC-00021 Phase 5 blow-up;
see test_concept_solve_extent_stays_at_display_scale):
    # same overlap-avoidance distance transform as FA2 (shared parent class)
    gravityForce = G * mass_i * mass_j / distance_eff**3
    force_on_i += (pos_j - pos_i) * gravityForce         # ∝ 1/d² magnitude
                                                          # (vs FA2's 1/d); NO
                                                          # degree factor
    # distance == 0: vis sets distance = dx = 0.1 deterministically (no Alea
    # here, unlike FA2). This port reuses its seeded-jitter correction for
    # both laws — same mechanism-over-byte-parity rationale as above.
    # vis's quadtree (theta) approximation is NOT mirrored: this port does
    # exact pairwise repulsion for both laws, which is strictly more accurate.

This module does exact O(n^2) pairwise repulsion (row-chunked to bound
temporaries), not vis's Barnes-Hut spatial tree approximation — a deliberate
simplification the spec sanctions for the <1500-node regime this ships for;
`repulsion_fn` below is an explicit seam for a future Barnes-Hut/grid solver.

Central gravity — vis has TWO gravity solvers, selected by *solver type* in
PhysicsEngine.init(): solver "forceAtlas2Based" gets
ForceAtlas2BasedCentralGravitySolver; every other type (barnesHut — the
default — repulsion, hierarchicalRepulsion) gets the base
CentralGravitySolver. So the etymology layouts (graph.js configures
forceAtlas2Based for both force-directed and era-layered) need the FA2
variant, while the concept map (concept-map.js configures barnesHut) needs
the base one. SolverParams.central_gravity_variant picks between them.

  Base variant (CentralGravitySolver._calculateForces):
    dx, dy = -pos_i                                      # vector from node to origin
    distance = |dx, dy|  (== |pos_i| by construction)
    gravityForce = 0 if distance == 0 else centralGravity / distance
    force_i += (dx, dy) * gravityForce
  Since |(dx,dy)| == distance, this force has *constant magnitude*
  centralGravity, always pointing toward the origin — distance-INDEPENDENT.

  FA2 variant (ForceAtlas2BasedCentralGravitySolver._calculateForces,
  overriding the base class's method):
    if distance > 0:
        degree = edge_count_i + 1                        # same degree as repulsion
        gravityForce = centralGravity * degree * mass_i
        force_i += (dx, dy) * gravityForce               # dx, dy NOT normalized
  Magnitude is centralGravity * degree * mass * distance — it grows LINEARLY
  with distance from the origin. (When distance == 0 vis skips the force
  assignment entirely, leaving the previous tick's value in place — a quirk
  this port doesn't reproduce: dx = dy = 0 there, so the contribution is
  zero either way in this fresh-sum-per-iteration model.)

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
from typing import Literal

import numpy as np

REPULSION_BLOCK_SIZE = 512


@dataclass(frozen=True)
class SolverParams:
    """Per-layout physics constants — mirrors graph.js's LAYOUTS registry /
    concept-map.js's physics options (gravitationalConstant, centralGravity,
    springConstant, damping, avoidOverlap, minVelocity, maxVelocity).

    central_gravity_variant selects between vis's two gravity solvers (see
    module docstring): "fa2" (ForceAtlas2BasedCentralGravitySolver — solver
    type forceAtlas2Based, the etymology layouts) or "base"
    (CentralGravitySolver — every other solver type, the concept map).

    repulsion_law likewise follows the layout's client solver type: "fa2"
    (ForceAtlas2BasedRepulsionSolver's 1/d law with the degree factor — the
    etymology layouts) or "barneshut" (BarnesHutSolver's 1/d² law, no degree
    factor — the concept map). Constants are calibrated per law; mixing them
    is the Phase 5 blow-up documented in the module docstring."""

    gravitational_constant: float
    central_gravity: float
    spring_constant: float
    damping: float
    avoid_overlap: float
    min_velocity: float
    max_velocity: float
    dt: float = 0.5
    max_iterations: int = 300
    central_gravity_variant: Literal["fa2", "base"] = "fa2"
    repulsion_law: Literal["fa2", "barneshut"] = "fa2"

    def __post_init__(self) -> None:
        # A typo'd variant would otherwise silently pick one law or the other.
        if self.central_gravity_variant not in ("fa2", "base"):
            msg = f"Unknown central_gravity_variant {self.central_gravity_variant!r}"
            raise ValueError(msg)
        if self.repulsion_law not in ("fa2", "barneshut"):
            msg = f"Unknown repulsion_law {self.repulsion_law!r}"
            raise ValueError(msg)


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
    law: Literal["fa2", "barneshut"] = "fa2",
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
            Ignored under the "barneshut" law, which has no degree factor.
        radius: (n,) estimated node radii for avoidOverlap.
        gravitational_constant: G (typically negative — repulsion).
        avoid_overlap: 0-1, vis's avoidOverlap option.
        rng: seeded generator for coincident-point jitter (determinism).
        block_size: row-chunk size bounding the (block, n) temporary matrices.
        law: which vis repulsion law to apply (see module docstring): "fa2"
            (1/d magnitude, degree factor) or "barneshut" (1/d², no degree).

    Returns:
        (n, 2) force array.

    Performance note: the per-pair force sum
    `forces[i] = sum_j gravityForce[i,j] * (pos[j] - pos[i])` is computed via
    the algebraic identity
    `= (gravityForce @ pos) - pos[i] * rowsum(gravityForce[i, :])`,
    turning an O(block*n*2) elementwise-multiply-then-reduce into a single
    BLAS matmul (block,n)@(n,2) plus a cheap row-sum — an exact
    reformulation, not an approximation (measured ~5x faster than the
    elementwise form at cupboard scale, ~940 nodes, on the profiling
    hardware used during development). One consequence: this needs squared
    distances rather than explicit (dx, dy) vectors, computed via
    `|a-b|^2 = |a|^2 + |b|^2 - 2 a.b` (another matmul) instead of a
    materialized (block, n, 2) difference array — so exactly-coincident
    pairs (dist == 0) can't be given a directional jitter this way (the true
    displacement is (0, 0), so no amount of pretending the *distance* is
    nonzero recovers a push direction). Those rare pairs are corrected in a
    separate, sparse pass after the main computation.
    """
    n = pos.shape[0]
    forces = np.zeros((n, 2), dtype=pos.dtype)
    if n <= 1 or gravitational_constant == 0:
        return forces

    overlap_avoidance_factor = 1 - min(1.0, max(0.0, avoid_overlap))
    has_radius = radius > 0
    sq_norms = (pos**2).sum(axis=-1)  # (n,)
    coincident_pairs: list[tuple[int, int]] = []

    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        block_pos = pos[start:end]  # (b, 2)
        block_mass = mass[start:end]  # (b,)
        block_degree = degree[start:end]  # (b,)
        block_radius = radius[start:end]  # (b,)
        block_has_radius = has_radius[start:end]
        b = end - start

        # dist_sq[bi, j] = |pos[j] - block_pos[bi]|^2, via the polarization
        # identity — avoids ever materializing a (b, n, 2) difference array.
        dot = block_pos @ pos.T  # (b, n) BLAS matmul
        dist_sq = np.maximum(sq_norms[start:end, np.newaxis] + sq_norms[np.newaxis, :] - 2 * dot, 0)

        row_idx = np.arange(b)
        self_cols = np.arange(start, end)
        dist_sq[row_idx, self_cols] = np.inf  # zero out self-interaction

        zero_mask = dist_sq == 0
        if np.any(zero_mask):
            bi_idx, j_idx = np.nonzero(zero_mask)
            for bi, j in zip(bi_idx, j_idx, strict=True):
                if start + bi < j:  # record each unordered pair once
                    coincident_pairs.append((start + bi, int(j)))
            dist_sq = np.where(zero_mask, 1.0, dist_sq)  # avoid /0 below; corrected separately

        dist = np.sqrt(dist_sq)

        if overlap_avoidance_factor < 1:
            radius_col = block_radius[:, np.newaxis]  # (b, 1), broadcasts over j
            adjusted = np.maximum(0.1 + overlap_avoidance_factor * radius_col, dist - radius_col)
            dist_eff = np.where(block_has_radius[:, np.newaxis], adjusted, dist)
        else:
            dist_eff = dist

        # fa2:       gravityForce[bi, j] = G * mass[bi] * mass[j] * degree[bi] / dist_eff^2
        # barneshut: gravityForce[bi, j] = G * mass[bi] * mass[j] / dist_eff^3
        # (each then multiplies the raw displacement, so the magnitudes go as
        # 1/d and 1/d² respectively — see module docstring)
        gravity_force = gravitational_constant * block_mass[:, np.newaxis] * mass[np.newaxis, :]
        if law == "barneshut":
            gravity_force = gravity_force / dist_eff**3
        else:
            gravity_force = gravity_force * block_degree[:, np.newaxis] / dist_eff**2
        gravity_force[row_idx, self_cols] = 0  # self column: exactly zero, not just ~0

        # sum_j gravityForce[bi,j] * (pos[j] - block_pos[bi])
        #   = (gravityForce @ pos) - block_pos * rowsum(gravityForce)
        weighted_pos = gravity_force @ pos  # (b, 2) BLAS matmul
        row_sum = gravity_force.sum(axis=1)  # (b,)
        forces[start:end] = weighted_pos - block_pos * row_sum[:, np.newaxis]

    if coincident_pairs:
        _apply_coincident_jitter(
            forces, pos, mass, degree, gravitational_constant, coincident_pairs, rng, law
        )

    return forces


def _apply_coincident_jitter(
    forces: np.ndarray,
    pos: np.ndarray,
    mass: np.ndarray,
    degree: np.ndarray,
    gravitational_constant: float,
    pairs: list[tuple[int, int]],
    rng: np.random.Generator,
    law: Literal["fa2", "barneshut"] = "fa2",
) -> None:
    """Sparse correction for exactly-coincident node pairs: the bulk matmul
    path can't give these a push direction (see default_repulsion_fn's
    docstring), so nudge them apart directly, matching the spec's seeded-
    jitter determinism requirement. Mutates `forces` in place."""
    jitter = 0.1 * rng.random(size=(len(pairs), 2)).astype(pos.dtype)
    distance = np.sqrt((jitter**2).sum(axis=-1))
    for (i, j), d, jit in zip(pairs, distance, jitter, strict=True):
        if law == "barneshut":
            gravity_force_i = gravitational_constant * mass[i] * mass[j] / d**3
            gravity_force_j = gravity_force_i  # no degree factor — symmetric
        else:
            gravity_force_i = gravitational_constant * mass[i] * mass[j] * degree[i] / d**2
            gravity_force_j = gravitational_constant * mass[j] * mass[i] * degree[j] / d**2
        forces[i] += jit * gravity_force_i
        forces[j] -= jit * gravity_force_j


def _central_gravity_forces(
    pos: np.ndarray,
    central_gravity: float,
    variant: str,
    mass: np.ndarray,
    degree: np.ndarray,
) -> np.ndarray:
    """Pull toward the origin, one of vis's two laws (see module docstring):
    "base" is constant-magnitude, "fa2" grows linearly with distance and
    scales with degree * mass."""
    n = pos.shape[0]
    if central_gravity == 0:
        return np.zeros((n, 2), dtype=np.float64)
    dxy = -pos
    if variant == "fa2":
        gravity_force = central_gravity * degree * mass
    else:
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
        repulsion_fn: swappable repulsion implementation (quadtree/grid seam);
            must accept the same signature as default_repulsion_fn, including
            the `law` keyword.
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
            cur_pos,
            mass,
            degree,
            radius,
            params.gravitational_constant,
            params.avoid_overlap,
            rng,
            law=params.repulsion_law,
        )
        forces += _central_gravity_forces(
            cur_pos, params.central_gravity, params.central_gravity_variant, mass, degree
        )
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
