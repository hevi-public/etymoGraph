"""Perf budget test for the full layout pipeline (SPC-00021 §6): cupboard-scale
(940 nodes) etymology graphs must solve well within the target used to size
the SSE frame cadence and the server-vs-client timing comparison.
"""

import time

import pytest
from app.services.layout import engine

CUPBOARD_SCALE_NODE_COUNT = 940
# A regression tripwire, not a target: the solve runs ~1.3 s on an idle M2 but
# 1.5-1.7 s under ambient load or on BLAS-poor numpy, which made a 1.5 s budget
# flake (RA follow-up on the SPC-00021 merge; observed again during Phase 5).
# Real regressions (e.g. losing the BLAS-matmul repulsion) show as 4-5x, so 2x
# headroom keeps the tripwire meaningful.
BUDGET_SECONDS = 3.0


def _synthetic_etymology_graph(node_count: int):
    """A branching tree loosely shaped like a real etymology graph: a short
    ancestor chain, then wide descendant fan-out across several levels —
    enough breadth for repulsion/springs to do real work, not a degenerate
    single chain."""
    nodes = [{"id": "root:PIE", "label": "root", "language": "Proto-Indo-European", "level": -2}]
    edges = []
    nodes.append(
        {"id": "mid:ProtoGermanic", "label": "mid", "language": "Proto-Germanic", "level": -1}
    )
    edges.append({"from": "mid:ProtoGermanic", "to": "root:PIE", "label": "inh"})
    nodes.append({"id": "word:English", "label": "word", "language": "English", "level": 0})
    edges.append({"from": "word:English", "to": "mid:ProtoGermanic", "label": "inh"})

    languages = ["English", "Old English", "Middle English", "German", "French", "Latin"]
    remaining = node_count - len(nodes)
    level = 1
    frontier = ["word:English"]
    i = 0
    while remaining > 0:
        next_frontier = []
        for parent in frontier:
            branch = min(3, remaining)
            if branch <= 0:
                break
            for _b in range(branch):
                node_id = f"n{i}:{languages[i % len(languages)]}"
                nodes.append(
                    {
                        "id": node_id,
                        "label": f"n{i}",
                        "language": languages[i % len(languages)],
                        "level": level,
                    }
                )
                edges.append({"from": node_id, "to": parent, "label": "der"})
                next_frontier.append(node_id)
                i += 1
                remaining -= 1
                if remaining <= 0:
                    break
            if remaining <= 0:
                break
        frontier = next_frontier or frontier
        level += 1
        if level > node_count:  # safety valve, should never trigger
            break

    assert len(nodes) == node_count
    return nodes, edges


@pytest.mark.tier0
@pytest.mark.slow
def test_cupboard_scale_force_directed_solves_within_budget():
    nodes, edges = _synthetic_etymology_graph(CUPBOARD_SCALE_NODE_COUNT)

    start = time.perf_counter()
    frames = list(engine.solve("force-directed", nodes, edges))
    elapsed = time.perf_counter() - start

    assert len(frames) > 0
    assert (
        elapsed < BUDGET_SECONDS
    ), f"force-directed solve took {elapsed:.2f}s, budget is {BUDGET_SECONDS}s"


@pytest.mark.tier0
@pytest.mark.slow
def test_cupboard_scale_era_layered_solves_within_budget():
    """era-layered runs up to 500 iterations (vs. 300 for force-directed) at
    much heavier damping — give it a looser budget, matching the spec's own
    wider estimate for this layout."""
    nodes, edges = _synthetic_etymology_graph(CUPBOARD_SCALE_NODE_COUNT)

    start = time.perf_counter()
    frames = list(engine.solve("era-layered", nodes, edges))
    elapsed = time.perf_counter() - start

    assert len(frames) > 0
    assert elapsed < BUDGET_SECONDS * 2, f"era-layered solve took {elapsed:.2f}s"
