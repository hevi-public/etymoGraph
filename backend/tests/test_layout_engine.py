"""Tests for the layout engine orchestration (families/seed/edge_params/fa2
wired together per layout)."""

import threading

import pytest
from app.services.layout import engine


def _etymology_graph():
    nodes = [
        {"id": "root:PIE", "label": "root", "language": "Proto-Indo-European", "level": -2},
        {"id": "mid:ProtoGermanic", "label": "mid", "language": "Proto-Germanic", "level": -1},
        {"id": "word:English", "label": "word", "language": "English", "level": 0},
        {"id": "child1:English", "label": "child1", "language": "English", "level": 1},
        {"id": "child2:English", "label": "child2", "language": "Old English", "level": 1},
    ]
    edges = [
        {"from": "mid:ProtoGermanic", "to": "root:PIE", "label": "inh"},
        {"from": "word:English", "to": "mid:ProtoGermanic", "label": "inh"},
        {"from": "child1:English", "to": "word:English", "label": "der"},
        {"from": "child2:English", "to": "word:English", "label": "der"},
    ]
    return nodes, edges


def _concept_graph():
    nodes = [
        {"id": f"w{i}:English", "label": f"w{i}", "language": "English", "level": None}
        for i in range(6)
    ]
    # A reasonably dense phonetic edge set (real concept maps are dense; a
    # too-sparse graph under concept's strong G=-8000 repulsion can take a
    # long time to settle, which isn't a bug, just unrepresentative physics).
    phonetic_edges = [
        {
            "source": nodes[i]["id"],
            "target": nodes[j]["id"],
            "similarity": 0.5,
            "turchin_match": False,
        }
        for i in range(len(nodes))
        for j in range(i + 1, len(nodes))
    ]
    etymology_edges = [
        {"source": "w0:English", "target": "w1:English", "relationship": "cognate"},
    ]
    return nodes, phonetic_edges, etymology_edges


@pytest.mark.tier0
def test_force_directed_pins_root_at_origin():
    nodes, edges = _etymology_graph()
    frames = list(engine.solve("force-directed", nodes, edges))
    for frame in frames:
        assert frame.positions["root:PIE"] == (0.0, 0.0)
    assert frames[-1].converged is True


@pytest.mark.tier0
def test_era_layered_keeps_y_fixed_per_tier_every_frame():
    nodes, edges = _etymology_graph()
    frames = list(engine.solve("era-layered", nodes, edges))
    expected_y = {
        "root:PIE": engine.ERA_TIERS[engine.get_era_tier("Proto-Indo-European")]["y"],
        "mid:ProtoGermanic": engine.ERA_TIERS[engine.get_era_tier("Proto-Germanic")]["y"],
        "word:English": engine.ERA_TIERS[engine.get_era_tier("English")]["y"],
        "child1:English": engine.ERA_TIERS[engine.get_era_tier("English")]["y"],
        "child2:English": engine.ERA_TIERS[engine.get_era_tier("Old English")]["y"],
    }
    for frame in frames:
        for node_id, expected in expected_y.items():
            assert frame.positions[node_id][1] == expected
    assert frames[-1].converged is True


@pytest.mark.tier0
def test_era_layered_and_concept_use_uniform_mass_one():
    nodes, _edges = _etymology_graph()
    root_id = engine.pick_etymology_root(nodes)
    for node in nodes:
        assert engine._mass_for("era-layered", node, root_id) == 1.0
        assert engine._mass_for("concept", node, root_id) == 1.0
    # force-directed differs: root is heavier, others decay by level.
    assert engine._mass_for("force-directed", nodes[0], root_id) == 4.0  # root itself
    non_root = next(n for n in nodes if n["id"] != root_id)
    assert engine._mass_for("force-directed", non_root, root_id) != 1.0 or non_root.get(
        "level"
    ) in (
        1,
        -1,
    )


@pytest.mark.tier0
def test_central_gravity_variant_matches_each_layouts_client_solver():
    """vis picks its central-gravity law by solver type (fa2.py module
    docstring): forceAtlas2Based — both etymology layouts in graph.js — runs
    the FA2 variant; barnesHut — concept-map.js — runs the base one. Rail:
    keep the server-side mapping in lockstep with the client solvers."""
    assert engine._LAYOUT_PARAMS["force-directed"].central_gravity_variant == "fa2"
    assert engine._LAYOUT_PARAMS["era-layered"].central_gravity_variant == "fa2"
    assert engine._LAYOUT_PARAMS["concept"].central_gravity_variant == "base"


@pytest.mark.tier0
def test_repulsion_law_matches_each_layouts_client_solver():
    """Same rail for the repulsion law (SPC-00021 Phase 5): each layout's
    constants are calibrated for the law its client solver runs — mixing
    them is the concept blow-up (see
    test_concept_solve_extent_stays_at_display_scale)."""
    assert engine._LAYOUT_PARAMS["force-directed"].repulsion_law == "fa2"
    assert engine._LAYOUT_PARAMS["era-layered"].repulsion_law == "fa2"
    assert engine._LAYOUT_PARAMS["concept"].repulsion_law == "barneshut"


@pytest.mark.tier0
def test_concept_seeds_from_etymology_edges_only():
    """The seed positions must come from compute_tree_positions over the
    etymology-derived vis edges only, not the phonetic edges — matching
    concept-map.js's own pre-Worker-response initial paint."""
    nodes, phonetic_edges, etymology_edges = _concept_graph()
    _prepared_a, seed_pos_a, root_a = engine.prepare_concept_graph(
        nodes, phonetic_edges, etymology_edges, include_etymology_edges=True
    )
    # Changing the phonetic edges (but not etymology edges) must not change
    # the seed positions at all, since seeding never looks at them.
    different_phonetic = [
        {
            "source": nodes[0]["id"],
            "target": nodes[-1]["id"],
            "similarity": 0.9,
            "turchin_match": True,
        }
    ]
    _prepared_b, seed_pos_b, root_b = engine.prepare_concept_graph(
        nodes, different_phonetic, etymology_edges, include_etymology_edges=True
    )
    assert root_a == root_b
    assert (seed_pos_a == seed_pos_b).all()


@pytest.mark.tier0
def test_unknown_layout_raises():
    nodes, edges = _etymology_graph()
    with pytest.raises(ValueError, match="Unknown layout"):
        list(engine.solve("bogus-layout", nodes, edges))


@pytest.mark.tier0
def test_only_the_last_frame_has_final_fields_populated():
    nodes, edges = _etymology_graph()
    frames = list(engine.solve("force-directed", nodes, edges))
    assert len(frames) > 1  # otherwise this test can't distinguish frame vs. final
    for frame in frames[:-1]:
        assert frame.converged is False
        assert frame.iterations is None
        assert frame.solve_ms is None
    last = frames[-1]
    assert last.iterations == last.i
    assert last.solve_ms is not None
    # No iteration number repeats between the last "frame" and the "final"
    # (this would indicate the final step was double-yielded).
    iterations_seen = [f.i for f in frames]
    assert len(iterations_seen) == len(set(iterations_seen))


@pytest.mark.tier0
def test_solve_is_deterministic_across_runs():
    nodes, edges = _etymology_graph()
    frames_a = list(engine.solve("force-directed", nodes, edges, algo_version="1"))
    frames_b = list(engine.solve("force-directed", nodes, edges, algo_version="1"))
    assert len(frames_a) == len(frames_b)
    for fa, fb in zip(frames_a, frames_b, strict=True):
        assert fa.positions == fb.positions
        assert fa.converged == fb.converged


@pytest.mark.tier0
def test_cancellation_stops_solve_early():
    nodes, edges = _etymology_graph()
    cancel = threading.Event()
    gen = engine.solve("force-directed", nodes, edges, cancel=cancel)
    frames = []
    for frame in gen:
        frames.append(frame)
        if len(frames) == 3:
            cancel.set()
    assert frames[-1].converged is False
    assert len(frames) < 300  # well under force-directed's max_iterations


@pytest.mark.tier0
def test_concept_solve_extent_stays_at_display_scale():
    """Regression for the SPC-00021 Phase 5 concept-layout blow-up: concept's
    G=-8000 was calibrated for vis's barnesHut 1/d² repulsion, but the solver
    applied the FA2 1/d law to every layout, so repulsion overpowered the
    springs by orders of magnitude and every concept solve at realistic size
    expanded to a velocity-clamp-limited ±8-11k px square (the live 54-node
    hound map reached ±7,700). A settled concept layout must stay at display
    scale — client physics puts a 137-node wine map within roughly ±1500 px.
    The graph shape mirrors a real concept map: Turchin-cluster cliques plus
    sparse cross-cluster similarity edges."""
    nodes = [
        {"id": f"w{i}:English", "label": f"w{i}", "language": "English", "level": None}
        for i in range(54)
    ]
    phonetic_edges = [
        {
            "source": nodes[i]["id"],
            "target": nodes[j]["id"],
            "similarity": 0.6,
            "turchin_match": True,
        }
        for i in range(54)
        for j in range(i + 1, 54)
        if i // 9 == j // 9  # cliques of 9 (Turchin clusters)
    ] + [
        {
            "source": nodes[c * 9]["id"],
            "target": nodes[((c + 1) % 6) * 9]["id"],
            "similarity": 0.4,
            "turchin_match": False,
        }
        for c in range(6)  # ring of weak cross-cluster links
    ]
    final = None
    for frame in engine.solve("concept", nodes, phonetic_edges=phonetic_edges):
        final = frame
    coords = [c for xy in final.positions.values() for c in xy]
    assert max(abs(c) for c in coords) < 3000, (
        f"concept layout exploded to ±{max(abs(c) for c in coords):.0f} px "
        "(repulsion law mismatch — see fa2.SolverParams.repulsion_law)"
    )
