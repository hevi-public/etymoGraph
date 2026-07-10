# SPC-00021 Decision Log

## Starting Question

"The frontend graph rendering with vis.js is really slow, as it animates every step in the
calculations, especially on larger graphs (couple of hundred nodes). I want to speed it up
significantly. To achieve that, we need to move the graph computation to the backend."

The prompt came with four explicit sub-questions: (1) is the current test harness good enough to
refactor against? (2) what language should the solver be in (GraalVM JS interop? Go/Rust?
step-by-step)? (3) can the frontend animation be kept so the UX feels the same (SSE-fed states +
simple adjustment)? (4) what else should be considered? Constraints: Docker deployment on a plain
server, no GPU; ML-predicted layouts acknowledged as experimental only.

Investigation confirmed the diagnosis and sharpened it: the cost is vis.js running `forceAtlas2Based`
with `stabilization: false`, rendering every solver tick until `minVelocity`. It also surfaced two
head starts — graph.js already contains a deterministic pure-JS seeding engine
(`computeTreePositions`, radial + barycentric), and the backend already has the concept-map
similarity math (`build_similarity_edges`) that the Web Worker duplicates — and one blocker:
`find_descendants` is non-deterministic (`.limit(50)`, no sort), so server layouts could not be
reproducible without fixing it first.

## Alternatives Considered

### Where the solver runs / language

| Option | Pros | Cons | Outcome |
|---|---|---|---|
| **Python + numpy in the existing FastAPI backend** | one service, one test framework (pytest tiers), reuses the precompute-collection pattern, executor keeps the event loop free; ≤1000 nodes solves well under budget | force loop must be re-derived from vis source; needs golden fixtures as a cross-language oracle | **Chosen** |
| Node sidecar reusing the JS (graphology-layout-forceatlas2) | zero port-divergence risk — literally the same functions; battle-tested FA2 | fourth container, second backend language, separate test story | Runner-up; rejected |
| GraalVM JS interop | "reuse the JS" without a rewrite | a JVM grafted onto a Python/JS stack to run ~300 lines of portable math; heavy images; interop complexity | Rejected outright |
| Rust/Go sidecar | raw speed, matters at 3000+ nodes | new toolchain + container + test story; premature before profiling | Deferred — `repulsion_fn` seam + follow-up spec keep the door open |
| ML layout prediction | potentially instant layouts | experimental, needs training data/serving/quality oracle; GPU-less serving unproven | Deferred (explicitly experimental per the prompt); the layout cache will accumulate a training corpus as a side effect |

### Animation / transport

| Option | Notes | Outcome |
|---|---|---|
| **SSE streaming of solver states, frontend tweens between frames** | matches the original proposal; needs nginx changes (HTTP/1.1 upstream, per-response unbuffering, longer read timeout) and an executor→queue bridge | **Chosen by the human** |
| Single response + client tween (recommended by the agent) | for typical graphs the solve finishes < 1 s, so a stream emits few frames; no streaming infra | Rejected in favor of SSE; its insight survives as the cache-hit path (`graph` + `final`, zero frames) |
| Keyframe replay in one JSON response | faithful settle without SSE | Rejected with the above |
| WebSockets | bidirectional not needed; heavier proxy story than SSE | Rejected |
| No animation (fade-in at final) | simplest | Rejected — losing the organic settle was explicitly undesired |

Design consequences of choosing SSE: the first event carries the full graph so server mode makes
one request and `/tree` stays byte-identical for the SPC-00013 snapshots; frames are full position
maps (droppable, idempotent) rather than deltas; `final` is always emitted.

### API shape

- Extend `/tree` with an opt-in `layout=` param — rejected: the SPC-00013 characterization suite
  asserts byte-for-byte equality on `/tree`; additive-but-in-place changes make every snapshot's
  blast radius ambiguous. Separate endpoints keep the old surface frozen and the new surface
  independently snapshotted.
- POST the topology to a layout service — rejected: EventSource is GET-only, and GET keyed by the
  same params as `/tree` gives cacheability; with the determinism fix, re-running TreeBuilder
  reproduces the identical graph, so the "duplicate DB work" objection dissolves (and cache hits
  skip it entirely).

### Filter/slider behavior (raised mid-review by the human)

Frontend toggles (etymology type checkboxes, layout dropdown, concept similarity slider,
etymology-edge toggle) change the solver's inputs. Options: client-side filtering without
re-layout (positions frozen; simplest, but layouts stop reflecting visible edges) vs re-request
the backend solve per change. **Human directed: send it back to the backend solver.** Adopted as:
every input-changing control closes the in-flight stream and re-requests (cache-keyed, so repeat
combinations are warm hits); the concept slider filters client-side *during* drag and re-solves on
release (debounced); surviving nodes keep their positions as tween start, so filter changes morph
rather than restart the layout.

### Testing groundwork depth

- Full SPC-00020 first (its own "net before surgery" rule) — safest, but a multi-day project
  before any perf work.
- Targeted net only (recommended initially by the agent).
- **Human's direction:** adopt the tiered BDD/TDD approach from the HAIP repo as the guiding
  aspiration — "obviously the current codebase is not built for it, so it's an aspiration, not a
  first step" — with an open question on how to test the graph layer at all. Investigation found
  SPC-00020 *is* that philosophy already adapted to this stack (it cites the `bdd-tiered-testing`
  skill). Resolution: align all new tests with SPC-00020's tiers and implement only its cheap
  Steps 1–3 (lifespan + `Depends`, ~12 net lines) so the SSE endpoints get hermetic in-process
  acceptance tests; the Step-4 repository port stays deferred. The "how do we test the graph
  layer" answer became §5/§9 of the spec: golden position fixtures generated from the existing JS
  as a cross-language oracle, solver invariant tests (fixed nodes immobile, determinism,
  convergence), SSE contract tests, and Playwright visual regression — which server-side
  determinism finally makes reliable.

### Scope

Force-directed only (smallest) vs both etymology layouts (default view included) vs everything.
**Human chose everything**: both etymology layouts *and* the concept map. The concept map turned
out cheaper than feared — the backend already owns the similarity math; the Worker becomes the
client-mode fallback.

## Decision & Rationale

Move layout computation into the existing Python backend as a numpy FA2-style solver seeded by a
faithful port of the client's deterministic layout engine; stream solver states over SSE
(`graph` → `frame*` → `final`) from new, additive endpoints; cache final positions in a `layouts`
collection keyed by request params + `algo_version`; frontend disables physics, tweens between
frames, re-requests the solver on any filter/slider change, and falls back to today's client
physics behind a `layoutMode` flag. Prerequisites first: deterministic `find_descendants`
(SPC-00014 R3 slice), golden fixtures for the port, real TreeBuilder tests over a small fake
collection, SPC-00020 Steps 1–3, and a measured perf baseline.

Rationale: the seeding engine already exists and is pure (port + verify, not invent); the backend
already owns topology, levels, and the concept similarity math; determinism + caching turn repeat
and shared-link loads into instant `graph`+`final` responses; SSE preserves the settle animation
the human wanted while the flag keeps a byte-identical rollback path; and every piece lands behind
tests placed on SPC-00020's tier ladder, moving the codebase toward the HAIP-style architecture
without blocking on it.

## Participants

- **Human (hevi)** — problem statement and framing questions; decisions: SSE streaming, everything
  in scope, Python + numpy, HAIP tiered BDD/TDD as testing aspiration, filters re-solve on the
  backend; will implement (starting on the Mac Mini).
- **Claude (planning session, 2026-07-04)** — codebase investigation via three parallel explore
  agents (frontend graph/physics; backend API/Docker; tests/specs/audit), design via a plan agent,
  direct verification of the layout engine, `find_descendants`, and `phonetic_similarity.py`;
  drafted this spec and log. Attempted to review the HAIP repo directly (`add_repo` approval did
  not come through); relied on SPC-00020 as its in-repo adaptation.

## Addendum — Phase 0d baseline measurement (2026-07-10)

The §5 "Perf baseline" harness (`tests/e2e/layout-baseline.spec.js`, `make bench-layout-baseline`)
was implemented and run after Phase 2. Three decisions made during that work, and one finding:

**Fixture-served trees.** At measurement time the local MongoDB data directory had lost the
`etymology.words` collection file (mongod fasserts on any word query; `data/raw/` was empty too,
so no reload without a fresh multi-hour download of a *newer* Kaikki dump than the fixtures were
captured from). Rather than block the baseline — or measure against drifted data — the harness
gained an opt-in `LAYOUT_BASELINE_FIXTURES=1` mode that fulfills `/api/etymology/{word}/tree` from
the SPC-00013 captures via Playwright request interception. The measured quantity
(`stabilized − network-created`, per §5) starts *after* the response is parsed, so serving the
captured production response changes nothing about the metric while pinning the exact graph
topology. Default mode still measures the live stack. Concept-map runs need live concept
resolution and are skipped in fixture mode; the concept baseline is deferred until the DB is
restored (`make update`).

**Timed-out runs are not repeated.** Layouts run under a fixed `randomSeed`, so a run that
produces no `stabilized` event within the timeout would repeat identically; the harness
short-circuits the remaining runs for that combination instead of burning 3 timeouts. The
"three runs, median" rule exists for wall-clock noise of *settled* runs and still applies there.

**Clamp diagnostics.** An unstabilized run reports the fraction of frames in which some node rode
the `maxVelocity` clamp, to distinguish a non-converging oscillation (fraction ≈ 1) from a merely
slow settle.

**Finding: era-layered never stabilizes on the client.** For every measured word, era-layered —
the *default* layout — produces no `stabilized` event at all (velocities pinned at the
`maxVelocity` clamp for 73–100% of frames; verified unchanged over 3+ minutes on cheese).
Mechanism: same-tier nodes on a fixed-Y band shoving each other via `avoidOverlap` — §11 risk 2
("era-layered 1D solve can oscillate") is not a porting risk but today's production behavior.
Consequences: SPC-00004 R5's stabilized→freeze never engages for era-layered (client physics runs,
and burns CPU, indefinitely), and the era-layered client baseline is "∞" — the server engine's
iteration cap (§6: 500 for era-layered) is the only thing that gives era-layered a settle time at
all.

**Participants:** Claude (autonomous implementation session, 2026-07-10) — harness, measurements,
this addendum. Human decision still owed: restoring the local dataset (`make update`) and rerunning
`make bench-layout-baseline` for the concept-map column.
