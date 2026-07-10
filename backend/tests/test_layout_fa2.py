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
@pytest.mark.parametrize("variant", ["fa2", "base"])
def test_central_gravity_pulls_free_node_toward_origin(variant):
    """A single free node, no edges, no repulsion partner, positive central
    gravity — it moves toward the origin under either gravity law."""
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
        central_gravity_variant=variant,
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


def _first_step_pull(x0, variant, *, mass=1.0, degree=1.0):
    """First-iteration displacement toward the origin of a single free node
    starting at (x0, 0) with only central gravity acting (no repulsion
    partner, no springs, zero initial velocity — so damping contributes
    nothing on this step and the displacement isolates the gravity law)."""
    pos = np.array([[x0, 0.0]])
    edges_i, edges_j, edge_k, edge_length = _no_edges()
    params = SolverParams(
        gravitational_constant=0.0,
        central_gravity=0.025,
        spring_constant=0.06,
        damping=0.5,
        avoid_overlap=0.0,
        min_velocity=0.001,
        max_velocity=50,
        max_iterations=1,
        central_gravity_variant=variant,
    )
    steps = _run_to_end(
        pos,
        np.array([mass]),
        np.array([degree]),
        np.zeros(1),
        np.array([False]),
        np.array([False]),
        edges_i,
        edges_j,
        edge_k,
        edge_length,
        params,
        seed_rng(["a"], "1"),
    )
    return x0 - steps[-1].pos[0, 0]


@pytest.mark.tier0
def test_fa2_central_gravity_grows_linearly_with_distance():
    """The forceAtlas2Based gravity law (used by both etymology layouts):
    pull magnitude is proportional to distance from the origin, so a node
    twice as far moves twice as far on the first step."""
    near = _first_step_pull(100.0, "fa2")
    far = _first_step_pull(200.0, "fa2")
    assert near > 0
    assert far == pytest.approx(2 * near)


@pytest.mark.tier0
def test_base_central_gravity_is_distance_independent():
    """The base gravity law (used by the barnesHut concept map): constant
    pull magnitude, so first-step displacement is the same at any distance."""
    near = _first_step_pull(100.0, "base")
    far = _first_step_pull(200.0, "base")
    assert near > 0
    assert far == pytest.approx(near)


@pytest.mark.tier0
def test_fa2_central_gravity_scales_with_degree_and_mass():
    """The FA2 law's force is centralGravity * degree * mass * distance:
    tripling degree triples the first-step pull, while mass cancels out of
    the resulting acceleration (F ∝ m, a = F/m) — so a heavier node moves
    exactly as far. Both discriminate the FA2 law from the base one, which
    ignores degree and slows heavier nodes."""
    base_pull = _first_step_pull(100.0, "fa2")
    assert _first_step_pull(100.0, "fa2", degree=3.0) == pytest.approx(3 * base_pull)
    assert _first_step_pull(100.0, "fa2", mass=4.0) == pytest.approx(base_pull)


@pytest.mark.tier0
def test_unknown_central_gravity_variant_is_rejected():
    """A typo'd variant must fail loudly at construction, not silently pick
    one gravity law."""
    with pytest.raises(ValueError, match="central_gravity_variant"):
        SolverParams(
            gravitational_constant=0.0,
            central_gravity=0.025,
            spring_constant=0.06,
            damping=0.5,
            avoid_overlap=0.0,
            min_velocity=0.001,
            max_velocity=50,
            central_gravity_variant="barnesHut",
        )


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


# --- barnesHut repulsion law (SPC-00021 Phase 5: the concept map's law) -----


@pytest.mark.tier0
def test_barneshut_repulsion_matches_the_pinned_vis_formula():
    """Hand-computed check against BarnesHutSolver._calculateForces (v9.1.9):
    force on i = (pos_j - pos_i) * G * m_i * m_j / d³, i.e. magnitude
    |G| * m_i * m_j / d² directed away from j for negative G — no degree
    factor, one power of d steeper than the FA2 law."""
    from app.services.layout.fa2 import default_repulsion_fn

    pos = np.array([[0.0, 0.0], [3.0, 4.0]])  # d = 5
    mass = np.array([2.0, 1.5])
    degree = np.array([7.0, 1.0])  # must be ignored under barneshut
    rng = seed_rng(["a", "b"], "3")

    forces = default_repulsion_fn(
        pos, mass, degree, np.zeros(2), -1000.0, 0.0, rng, law="barneshut"
    )

    # gravityForce = G*m_i*m_j/d³ = -1000*3/125 = -24; force_0 = (3,4)*-24
    np.testing.assert_allclose(forces[0], [-72.0, -96.0], rtol=1e-12)
    np.testing.assert_allclose(forces[1], [72.0, 96.0], rtol=1e-12)


@pytest.mark.tier0
def test_barneshut_repulsion_ignores_degree_where_fa2_scales_with_it():
    """The degree factor is FA2-only: changing degrees must change FA2 forces
    and leave barnesHut forces untouched."""
    from app.services.layout.fa2 import default_repulsion_fn

    pos = np.array([[0.0, 0.0], [100.0, 0.0]])
    mass = np.ones(2)
    low = np.array([1.0, 1.0])
    high = np.array([9.0, 9.0])
    rng = seed_rng(["a", "b"], "3")

    bh_low = default_repulsion_fn(pos, mass, low, np.zeros(2), -8000.0, 0.0, rng, law="barneshut")
    bh_high = default_repulsion_fn(pos, mass, high, np.zeros(2), -8000.0, 0.0, rng, law="barneshut")
    np.testing.assert_array_equal(bh_low, bh_high)

    fa2_low = default_repulsion_fn(pos, mass, low, np.zeros(2), -8000.0, 0.0, rng, law="fa2")
    fa2_high = default_repulsion_fn(pos, mass, high, np.zeros(2), -8000.0, 0.0, rng, law="fa2")
    np.testing.assert_allclose(fa2_high, 9 * fa2_low, rtol=1e-12)


@pytest.mark.tier0
def test_barneshut_coincident_nodes_get_a_seeded_push_apart():
    """Exactly-coincident nodes can't get a direction from the matmul path;
    the seeded jitter pass must still push them apart under the barneshut law,
    deterministically."""
    from app.services.layout.fa2 import default_repulsion_fn

    pos = np.zeros((2, 2))
    mass = np.ones(2)
    degree = np.ones(2)

    forces_a = default_repulsion_fn(
        pos, mass, degree, np.zeros(2), -8000.0, 0.0, seed_rng(["a", "b"], "3"), law="barneshut"
    )
    forces_b = default_repulsion_fn(
        pos, mass, degree, np.zeros(2), -8000.0, 0.0, seed_rng(["a", "b"], "3"), law="barneshut"
    )
    assert np.abs(forces_a).max() > 0
    np.testing.assert_array_equal(forces_a, forces_b)  # seeded → bit-identical
    np.testing.assert_allclose(forces_a[0], -forces_a[1])  # pushed apart symmetrically


@pytest.mark.tier0
def test_unknown_repulsion_law_is_rejected():
    with pytest.raises(ValueError, match="repulsion_law"):
        SolverParams(
            gravitational_constant=-350,
            central_gravity=0.0,
            spring_constant=0.06,
            damping=0.5,
            avoid_overlap=0.0,
            min_velocity=2.0,
            max_velocity=50,
            repulsion_law="quadtree",
        )


@pytest.mark.tier0
def test_barneshut_overlap_avoidance_uses_the_receivers_radius():
    """avoid_overlap replaces the pair distance with
    max(0.1 + (1-avoidOverlap)*radius_i, d - radius_i) for the RECEIVING node
    only (vis BarnesHutSolver parent-class semantics). Production concept
    solves run avoid_overlap=0.5 with real radii, so the transform must be
    pinned under the barneshut law too, not only at avoid_overlap=0."""
    from app.services.layout.fa2 import default_repulsion_fn

    pos = np.array([[0.0, 0.0], [3.0, 4.0]])  # d = 5
    mass = np.ones(2)
    degree = np.ones(2)
    radius = np.array([2.0, 0.0])
    rng = seed_rng(["a", "b"], "3")

    forces = default_repulsion_fn(pos, mass, degree, radius, -1000.0, 0.5, rng, law="barneshut")

    # node 0 (radius 2): dist_eff = max(0.1 + 0.5*2, 5-2) = 3 → (3,4) * -1000/27
    np.testing.assert_allclose(forces[0], [-1000.0 / 9.0, -4000.0 / 27.0], rtol=1e-12)
    # node 1 (radius 0): transform skipped → dist_eff = 5 → (-3,-4) * -1000/125
    np.testing.assert_allclose(forces[1], [24.0, 32.0], rtol=1e-12)
