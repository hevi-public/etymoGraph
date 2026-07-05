"""Invariant tests for the fa2 numeric solver.

There's no JS/oracle parity possible here (this is genuinely new numeric
code — the JS side never ran a real force solver server-side), so these
test structural invariants the solver must hold regardless of exact tuning:
fixed axes never move, reruns are bit-identical, simple two/three-body
configurations move in the physically expected direction, and convergence
happens within the iteration budget.
"""

import threading

import numpy as np
import pytest
from app.services.layout.fa2 import (
    SolverParams,
    estimate_node_radius,
    run,
    seed_rng,
)


def _no_edges():
    return (
        np.zeros(0, dtype=np.int32),
        np.zeros(0, dtype=np.int32),
        np.zeros(0, dtype=np.float64),
        np.zeros(0, dtype=np.float64),
    )


def _run_to_end(*args, **kwargs) -> list:
    return list(run(*args, **kwargs))


@pytest.mark.tier0
def test_fixed_axes_never_move():
    """A node with fixed_x=fixed_y=True stays exactly at its initial position,
    even surrounded by strong repulsion/gravity from free neighbors."""
    pos = np.array([[0.0, 0.0], [50.0, 0.0], [-50.0, 0.0]])
    mass = np.array([4.0, 1.0, 1.0])
    degree = np.array([2.0, 1.0, 1.0])
    radius = np.zeros(3)
    fixed_x = np.array([True, False, False])
    fixed_y = np.array([True, False, False])
    edges_i, edges_j, edge_k, edge_length = _no_edges()
    params = SolverParams(
        gravitational_constant=-350,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.5,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=50,
    )
    rng = seed_rng(["root", "a", "b"], "1")
    steps = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
    )
    for step in steps:
        assert step.pos[0, 0] == 0.0
        assert step.pos[0, 1] == 0.0


@pytest.mark.tier0
def test_reruns_are_bit_identical():
    """Same seed, same inputs -> exactly the same sequence of positions."""
    pos = np.array([[0.0, 0.0], [30.0, 10.0], [-20.0, 15.0], [5.0, -40.0]])
    mass = np.array([4.0, 1.0, 1.0, 1.0])
    degree = np.array([3.0, 1.0, 1.0, 1.0])
    radius = np.array(
        [
            estimate_node_radius(4),
            estimate_node_radius(3),
            estimate_node_radius(5),
            estimate_node_radius(2),
        ]
    )
    fixed_x = np.array([True, False, False, False])
    fixed_y = np.array([True, False, False, False])
    edges_i = np.array([0, 0, 0], dtype=np.int32)
    edges_j = np.array([1, 2, 3], dtype=np.int32)
    edge_k = np.array([0.06, 0.06, 0.06])
    edge_length = np.array([120.0, 120.0, 120.0])
    params = SolverParams(
        gravitational_constant=-350,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.5,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=100,
    )
    node_ids = ["root", "a", "b", "c"]

    steps1 = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        seed_rng(node_ids, "1"),
    )
    steps2 = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        seed_rng(node_ids, "1"),
    )

    assert len(steps1) == len(steps2)
    for s1, s2 in zip(steps1, steps2, strict=True):
        assert np.array_equal(s1.pos, s2.pos)
        assert s1.max_velocity == s2.max_velocity
        assert s1.converged == s2.converged


@pytest.mark.tier0
def test_two_nodes_repel_apart():
    """Two free, coincident-ish nodes with no springs and negative G (repulsion)
    end up farther apart than they started."""
    pos = np.array([[0.0, 0.0], [1.0, 0.0]])
    mass = np.array([1.0, 1.0])
    degree = np.array([1.0, 1.0])
    radius = np.zeros(2)
    fixed_x = np.array([False, False])
    fixed_y = np.array([False, False])
    edges_i, edges_j, edge_k, edge_length = _no_edges()
    params = SolverParams(
        gravitational_constant=-350,
        central_gravity=0.0,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.0,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=30,
    )
    rng = seed_rng(["a", "b"], "1")
    steps = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
    )
    final = steps[-1].pos
    initial_dist = np.linalg.norm(pos[0] - pos[1])
    final_dist = np.linalg.norm(final[0] - final[1])
    assert final_dist > initial_dist


@pytest.mark.tier0
def test_spring_pulls_stretched_edge_toward_rest_length():
    """Two nodes far apart, connected by one spring, no repulsion/gravity —
    they move closer together (toward the spring's rest length)."""
    pos = np.array([[0.0, 0.0], [500.0, 0.0]])
    mass = np.array([1.0, 1.0])
    degree = np.array([1.0, 1.0])
    radius = np.zeros(2)
    fixed_x = np.array([False, False])
    fixed_y = np.array([False, False])
    edges_i = np.array([0], dtype=np.int32)
    edges_j = np.array([1], dtype=np.int32)
    edge_k = np.array([0.06])
    edge_length = np.array([120.0])
    params = SolverParams(
        gravitational_constant=0.0,
        central_gravity=0.0,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.0,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=100,
    )
    rng = seed_rng(["a", "b"], "1")
    steps = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
    )
    final = steps[-1].pos
    final_dist = np.linalg.norm(final[0] - final[1])
    assert final_dist < 500.0


@pytest.mark.tier0
def test_central_gravity_pulls_free_node_toward_origin():
    """A single free node, no edges, no repulsion partner, positive central
    gravity — it moves toward the origin."""
    pos = np.array([[100.0, 0.0]])
    mass = np.array([1.0])
    degree = np.array([1.0])
    radius = np.zeros(1)
    fixed_x = np.array([False])
    fixed_y = np.array([False])
    edges_i, edges_j, edge_k, edge_length = _no_edges()
    params = SolverParams(
        gravitational_constant=0.0,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.9,
        avoid_overlap=0.0,
        min_velocity=0.001,
        max_velocity=50,
        max_iterations=20,
    )
    rng = seed_rng(["a"], "1")
    steps = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
    )
    assert steps[-1].pos[0, 0] < 100.0
    assert steps[-1].pos[0, 0] >= 0.0  # heavy damping shouldn't overshoot past the origin


@pytest.mark.tier0
def test_converges_within_iteration_cap_for_a_calm_system():
    """A small system with reasonable constants stabilizes (max velocity
    below threshold) before exhausting the iteration cap."""
    pos = np.array([[0.0, 0.0], [40.0, 0.0], [-40.0, 0.0], [0.0, 40.0]])
    mass = np.array([4.0, 1.0, 1.0, 1.0])
    degree = np.array([3.0, 1.0, 1.0, 1.0])
    radius = np.zeros(4)
    fixed_x = np.array([True, False, False, False])
    fixed_y = np.array([True, False, False, False])
    edges_i = np.array([0, 0, 0], dtype=np.int32)
    edges_j = np.array([1, 2, 3], dtype=np.int32)
    edge_k = np.array([0.06, 0.06, 0.06])
    edge_length = np.array([120.0, 120.0, 120.0])
    params = SolverParams(
        gravitational_constant=-350,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.5,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=300,
    )
    rng = seed_rng(["root", "a", "b", "c"], "1")
    steps = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
    )
    assert steps[-1].converged is True
    assert len(steps) < params.max_iterations


@pytest.mark.tier0
def test_cancellation_stops_the_solver_early():
    """Setting the cancel event stops iteration before the cap, with the
    final yielded step marked not converged."""
    pos = np.array([[0.0, 0.0], [40.0, 0.0]])
    mass = np.array([1.0, 1.0])
    degree = np.array([1.0, 1.0])
    radius = np.zeros(2)
    fixed_x = np.array([False, False])
    fixed_y = np.array([False, False])
    edges_i, edges_j, edge_k, edge_length = _no_edges()
    params = SolverParams(
        gravitational_constant=-350,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.0,
        min_velocity=0.0001,  # unreachable -> would otherwise run to the cap
        max_velocity=50,
        max_iterations=1000,
    )
    rng = seed_rng(["a", "b"], "1")
    cancel = threading.Event()

    gen = run(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
        cancel=cancel,
    )
    steps = []
    for step in gen:
        steps.append(step)
        if len(steps) == 5:
            cancel.set()

    assert len(steps) < params.max_iterations
    assert steps[-1].converged is False


@pytest.mark.tier0
@pytest.mark.slow
def test_repulsion_scales_to_hundreds_of_nodes_quickly():
    """Sanity perf check on the raw solver (not the full engine pipeline,
    which gets its own budgeted test once engine.py exists): a few hundred
    random nodes should solve in well under a second per iteration batch."""
    import time

    rng_np = np.random.default_rng(7)
    n = 300
    pos = rng_np.uniform(-200, 200, size=(n, 2))
    mass = np.ones(n)
    degree = np.ones(n)
    radius = np.full(n, 30.0)
    fixed_x = np.zeros(n, dtype=bool)
    fixed_y = np.zeros(n, dtype=bool)
    edges_i = np.arange(0, n - 1, dtype=np.int32)
    edges_j = np.arange(1, n, dtype=np.int32)
    edge_k = np.full(n - 1, 0.06)
    edge_length = np.full(n - 1, 120.0)
    params = SolverParams(
        gravitational_constant=-350,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.5,
        min_velocity=2.0,
        max_velocity=50,
        max_iterations=60,
    )
    rng = seed_rng([str(i) for i in range(n)], "1")

    start = time.perf_counter()
    steps = _run_to_end(
        pos,
        mass,
        degree,
        radius,
        fixed_x,
        fixed_y,
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        rng,
    )
    elapsed = time.perf_counter() - start

    assert len(steps) > 0
    assert elapsed < 5.0
