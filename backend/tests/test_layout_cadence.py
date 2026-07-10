"""Tier 0 tests for the SSE frame-cadence policy (SPC-00021 §7/§9).

``_run_solver`` is driven directly with a stub ``_SolveJob`` and a
list-appending ``offer`` callback — no queue, no HTTP, no Mongo; the layout
engine underneath runs for real (pure numpy), so these stay Tier 0. The 80 ms
throttle reads wall-clock, so exact frame counts are machine-dependent; what
IS deterministic — and asserted here — are the policy's bounds: frames land
only on stride multiples (``stride = ceil(iteration_budget / _FRAME_TARGET)``),
the first stride hit always emits, consecutive frames are at least
``_MIN_FRAME_INTERVAL_MS`` apart, at most ``_FRAME_TARGET`` frames per solve,
and the offer sequence always terminates ``final``/``error`` → ``done``.
"""

import itertools
import logging
import math
import threading

import pytest
from app.routers import layout
from app.services.layout import LAYOUT_ALGO_VERSION, engine


def _chain_graph(n: int):
    """A single inh chain, big enough that every layout runs well past one
    frame stride before settling (empirically at n=40: force-directed hits
    its 300-iteration cap; era-layered converges around iteration ~276 —
    both far beyond their strides of 25 and 42)."""
    nodes = [
        {"id": f"n{i}:Lang", "label": f"node{i}", "language": "English", "level": i - 2}
        for i in range(n)
    ]
    edges = [{"from": f"n{i}:Lang", "to": f"n{i - 1}:Lang", "label": "inh"} for i in range(1, n)]
    return nodes, edges


def _job(layout_name: str = "force-directed", nodes=None, edges=None) -> layout._SolveJob:
    if nodes is None:
        nodes, edges = _chain_graph(40)
    return layout._SolveJob(
        layout=layout_name,
        graph={"nodes": nodes, "edges": edges},
        node_ids=[n.get("id", "?") for n in nodes],
        edge_count=len(edges),
        solve_kwargs={
            "layout": layout_name,
            "nodes": nodes,
            "edges": edges,
            "algo_version": LAYOUT_ALGO_VERSION,
        },
        cache_params={},
        graph_hash="",
    )


def _run(job: layout._SolveJob, cancel: threading.Event | None = None) -> list[tuple]:
    offered: list[tuple] = []
    layout._run_solver(job, cancel or threading.Event(), offered.append)
    return offered


@pytest.mark.tier0
def test_offer_sequence_is_frames_then_final_then_done():
    offered = _run(_job())
    kinds = [kind for kind, _ in offered]
    assert kinds.count("final") == 1
    assert kinds.count("done") == 1
    assert kinds[-2:] == ["final", "done"]
    assert offered[-1] == ("done", None)
    frames = kinds[:-2]
    assert frames, "a solve that outlives one stride must stream at least one frame"
    assert set(frames) == {"frame"}


@pytest.mark.tier0
@pytest.mark.parametrize("layout_name", ["force-directed", "era-layered"])
def test_frames_land_on_stride_multiples(layout_name):
    stride = math.ceil(engine.iteration_budget(layout_name) / layout._FRAME_TARGET)
    offered = _run(_job(layout_name))
    frame_is = [payload["i"] for kind, payload in offered if kind == "frame"]
    # The first stride hit always emits (nothing precedes it to throttle
    # against), pinning the ~_FRAME_TARGET-frames-per-solve derivation per
    # layout budget; later hits may be wall-clock-suppressed.
    assert frame_is and frame_is[0] == stride
    assert all(i % stride == 0 for i in frame_is)
    assert frame_is == sorted(set(frame_is)), "frame iterations must be strictly increasing"
    assert len(frame_is) <= layout._FRAME_TARGET


@pytest.mark.tier0
def test_consecutive_frames_respect_min_interval():
    # On fast hardware the throttle usually collapses this to a single frame
    # (vacuous pass); if the 80 ms gate is ever dropped, a full-budget solve
    # emits a frame every stride (~2 ms apart here) and these pairs fail.
    offered = _run(_job())
    times = [payload["t_ms"] for kind, payload in offered if kind == "frame"]
    for earlier, later in itertools.pairwise(times):
        assert later - earlier >= layout._MIN_FRAME_INTERVAL_MS


@pytest.mark.tier0
def test_payloads_carry_stats_and_wire_rounded_positions():
    job = _job()
    offered = _run(job)
    node_ids = set(job.node_ids)
    for kind, payload in offered:
        if kind not in ("frame", "final"):
            continue
        assert set(payload["positions"]) == node_ids
        for x, y in payload["positions"].values():
            assert x == round(x, 1)
            assert y == round(y, 1)
    final = next(payload for kind, payload in offered if kind == "final")
    assert final["algo_version"] == LAYOUT_ALGO_VERSION
    assert isinstance(final["iterations"], int)
    assert isinstance(final["converged"], bool)
    assert final["solve_ms"] > 0


@pytest.mark.tier0
def test_cancel_before_start_still_offers_final_then_done():
    cancel = threading.Event()
    cancel.set()
    offered = _run(_job(), cancel)
    assert [kind for kind, _ in offered] == ["final", "done"]
    assert offered[0][1]["converged"] is False


@pytest.mark.tier0
def test_engine_failure_offers_error_then_done_and_logs(caplog):
    # A node with no "id" makes the engine raise on its first iteration.
    job = _job(nodes=[{"label": "orphan", "language": "English", "level": 0}], edges=[])
    with caplog.at_level(logging.WARNING, logger="app.routers.layout"):
        offered = _run(job)
    assert [kind for kind, _ in offered] == ["error", "done"]
    assert offered[0][1] == {"message": "layout solve failed"}
    record = next(r for r in caplog.records if getattr(r, "event", "") == "layout.solve.failed")
    assert record.levelno == logging.WARNING


@pytest.mark.tier0
def test_unknown_layout_still_offers_error_then_done():
    # Even a job whose layout the engine rejects (unreachable via the
    # endpoints, which validate first) must terminate the offer sequence:
    # if "done" never arrives, the SSE read loop heartbeats forever.
    offered = _run(_job("diagonal"))
    assert [kind for kind, _ in offered] == ["error", "done"]
