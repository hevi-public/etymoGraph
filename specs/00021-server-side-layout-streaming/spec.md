# SPC-00021: Server-Side Graph Layout with SSE Streaming

| Field | Value |
|---|---|
| **Status** | approved |
| **Created** | 2026-07-04 |
| **Modifies** | SPC-00004 (supersedes its client-physics premise and constraint 12 "all changes in graph.js, do not modify the backend"; its LOD/clustering/straight-edge mitigations survive), SPC-00002 (concept map physics moves server-side; phonetic edges computed by the backend instead of the Web Worker), SPC-00014 (pulls its R3 deterministic-cap slice forward as an interim alphabetical sort), SPC-00020 (implements its Steps 1–3 DI seam + tier markers early; Step 4 port unchanged) |
| **Modified-by** | — |

---

**Context:** vis.js runs its force solver with `stabilization: false`, so every physics tick is
rendered live until the graph reaches `minVelocity`. On graphs of a couple hundred nodes and up
(fire=263, hound=464, wine=540, cupboard=940 with `types=inh,bor,der,cog`) this means seconds of
main-thread jank before the graph settles. This spec moves layout computation to the Python
backend: a numpy solver streams position states over **Server-Sent Events**, and the frontend only
tweens nodes between frames with physics disabled. Client-side physics is retained verbatim as a
fallback path behind a feature flag.

Two head starts make this a port, not a rewrite:

1. `graph.js:347-644` already contains a **deterministic pure-JS layout engine**
   (`computeTreePositions` → BFS spanning tree → radial rings / linear tree →
   `applyBarycentricRefinement`) used today to seed physics. It is the port source and the
   golden-fixture oracle.
2. `backend/app/services/phonetic_similarity.py::build_similarity_edges` already implements
   exactly what `similarity-worker.js` computes (same normalized Levenshtein over
   `dolgo_consonants`, same Turchin `dolgo_first2` rule, same `shared_classes` prefix, same
   rounding). Server-side concept edges are a wiring job plus an optional vectorized twin.

## 1. Problem

1. **Live physics animation is the bottleneck.** `stabilization: false` + `minVelocity` settling
   renders every solver tick. SPC-00004's mitigations (LOD, clustering, straight edges, physics
   freeze after `stabilized`) reduce *rendering* cost but the pre-`stabilized` simulation still
   runs on the client, on the main thread, on every load.
2. **Every client pays the full cost, every time.** Layouts are recomputed per visit; nothing is
   cached or shared.
3. **Server-side layout is currently impossible to do reproducibly**:
   `tree_builder.find_descendants` does `.limit(50)` with **no sort**, so identical requests can
   return different node sets (AUDIT-2026-06 A3 / SPC-00014 R3).
4. **The code being moved has no tests.** `computeTreePositions` and friends: zero coverage. The
   `TreeBuilder` async orchestration: vacuous stubs. The only `/tree` net (SPC-00013 snapshots)
   requires a live stack and skips-as-pass.

## 2. Goals

- Time from search to settled graph on cupboard (940 nodes): **< 2.5 s cold, < 0.8 s warm
  (cache hit)**; fire (263 nodes) **< 1.2 s cold**. Baseline measured in Phase 0 and recorded in §10.
- No physics simulation on the client in server mode; main-thread frames < 16 ms during settle.
- The settle still *animates*: solver states stream via SSE and the frontend tweens between them,
  so the UX keeps today's organic feel.
- First paint is not slower than today (client seeding still renders frame-0 instantly).
- `GET /api/etymology/{word}/tree` and `GET /api/concept-map` stay **byte-identical** (SPC-00013
  characterization holds). All layout features ship on new, additive endpoints.
- Deterministic layouts: same request → same positions (stronger shareable links).
- Client physics path preserved behind a flag: `layoutMode=client` is today's behavior exactly.

**Non-goals** (see §11): Barnes-Hut/grid approximation for 3000+ nodes; ML layout prediction;
SPC-00020 Step 4 repository port; SPC-00014's out-degree descendant ranking; WebSockets.

## 3. Architecture

```
search / filter change
        │
        ▼
frontend (flag: layoutMode=server)
        │  GET /api/etymology/{word}/tree/layout/stream?...   (EventSource)
        ▼
backend router ──► TreeBuilder (topology, on event loop)
        │                │
        │           cache hit? ──► emit graph + final immediately
        │                │ miss
        │                ▼
        │        layout engine (numpy, run_in_executor)
        │           seed (port of computeTreePositions)
        │           FA2-style iterations ──► frames via asyncio.Queue
        ▼
SSE: graph → frame* → final          (final written through to `layouts` collection)
        │
        ▼
frontend: physics disabled, rAF tween between frames; drag keeps local physics micro-adjust
fallback: stream error/timeout → today's /tree + client physics path
```

## 4. R1 — Determinism prerequisite (SPC-00014 R3 slice)

- `backend/app/services/tree_builder.py` (`find_descendants`, ~line 215): add
  `.sort([("word", 1), ("lang", 1), ("pos", 1), ("etymology_number", 1)])` between `find()` and
  `.limit(MAX_DESCENDANTS_PER_NODE)`. `(word, lang)` is the dedup key, so this makes both *which*
  50 docs survive the cap and their iteration order deterministic; `pos`/`etymology_number` break
  ties content-based (stable across DB reloads, unlike `_id`). Mongo performs a bounded top-k sort
  because `limit` is present.
- This is an **interim** deterministic cap. SPC-00014 later upgrades the ranking to
  out-degree-first ("most important branches survive"); alphabetical is forward-compatible and
  removes the reproducibility blocker now.
- Regenerate SPC-00013 fixtures (`make collect-fixtures`), human-review the diff (words with > 50
  descendants per ancestor may change node sets), commit fix + fixtures together.

## 5. R2 — Test groundwork (tiers per SPC-00020; groundwork only, not the Step-4 port)

- **JS layout goldens** — new `frontend/tests/layout-goldens.test.js` (reuses the eval-the-source
  harness from `graph-perf.test.js`); goldens live in `tests/fixtures/layout/` (repo root, so
  pytest reads the same files). Regeneration: `UPDATE_LAYOUT_GOLDENS=1 npx vitest run …` writes via
  `node:fs`; normal runs assert. Coverage:
  1. `computeTreePositions` radial path incl. barycentric refinement + disconnected-node fan;
  2. `computeLinearTreePositions` path (concept shape);
  3. era machinery: `getEraTier`, `groupNodesByTierAndFamily`, `assignFamilyClusterPositions`,
     `buildExtraEdges` invisible springs (incl. computed spring lengths);
  4. `classifyLang` family map over every distinct language in the fixtures — the JS/Python
     parity lock;
  5. per-edge physics params from `buildVisEdges` (degree-based `length`/`springConstant`) and
     concept `similarityToEdgeLength`/`buildConceptEdges`.
  Inputs: trimmed trees from `tests/fixtures/wiktionary/{cheese,dog,fire}.json` + 2–3 synthetic
  graphs (disconnected, single-node, deep chain).
- **TreeBuilder tests** — new `backend/tests/fakes.py`: `FakeWordsCollection` (~120 lines)
  implementing only the surface used (`find_one`, `find` → cursor with `.sort/.limit/.to_list/
  async for`, `$elemMatch` matcher for `name.$in`/`args.2`/`args.3`, `.database["etymology_edges"]`
  hop). Fill the three vacuous async stubs in `test_tree_builder.py`: `expand_word` (levels,
  ancestor edges, mention fallback), `find_descendants` (immediate-parent guard, depth cap,
  sorted-order determinism), `expand_cognates` (round cap, cycle termination). This is SPC-00020's
  named "smaller intermediate option" — raw-collection fake, no repository port.
- **Markers** — register `tier0 tier1 tier2 acceptance live` in `pyproject.toml`
  `[tool.pytest.ini_options]`.
- **DI Steps 1–3 (SPC-00020)** — lifespan-created Motor client in `main.py` (`app.state`),
  `Depends`-able providers in `database.py`, convert the 6 router call-sites; add `httpx` to
  `backend/requirements-dev.txt`. Blast radius per SPC-00020: 4 files, ~12 net lines, reversible.
  This unlocks in-process ASGI acceptance tests for the SSE endpoints (no live stack, no
  skips-as-pass).
- **Perf baseline** — new `tests/e2e/layout-baseline.spec.js` (env-gated via `LAYOUT_BASELINE`,
  never in CI) + `make bench-layout-baseline`: install a `window.__etymoNetwork` setter via
  `page.addInitScript`, measure `stabilized − network-created` and long-frame (> 33 ms) count for
  cheese/fire/hound/wine/cupboard × both layouts (concept map: poll `physics.stabilized`). Three
  runs, median. Record the table in §10.

## 6. R3 — Backend layout engine

New package `backend/app/services/layout/`; add `numpy>=2,<3` to `backend/requirements.txt`.

| Module | Contents |
|---|---|
| `__init__.py` | exports + `LAYOUT_ALGO_VERSION = "1"` (bump ⇒ cache invalidation + snapshot regen) |
| `families.py` | ports of `LANG_FAMILIES`/`classifyLang`, `ERA_TIERS`/`getEraTier` (incl. `DEEP_PROTO`/`CLASSICAL_SPECIFIC` regexes), tier+family grouping, family-cluster X seeding, invisible intra-family springs (`buildExtraEdges` formula) |
| `seed.py` | port of `computeTreePositions`: BFS spanning tree with **insertion-ordered adjacency matching JS iteration order**, radial angular spans, linear tree, disconnected fan, barycentric refinement (3 passes, damping 0.5, JS loop order) |
| `edge_params.py` | port of degree-based per-edge `length`/`springConstant` + concept edge formulas |
| `fa2.py` | the solver (below) |
| `phonetic_numpy.py` | vectorized pairwise Dolgopolsky Levenshtein + Turchin mask; exact-equality-tested against `build_similarity_edges` (the oracle) |
| `engine.py` | orchestration: seeds (radial ×0.35 mirroring `graph.js:1052-1061`; era X/Y; concept linear ×0.3), masses (`4/2^|level|`, root 4, era mass 1), constraint masks, yields a `FrameState` iterator, honors a cancellation `threading.Event` |

**Solver (`fa2.py`)**: float32 `pos/vel(n,2)`, `mass(n)`, `fixed_x/fixed_y` masks (root pin at
(0,0); era-layered `fixed_y` per tier band), per-edge `k`/`L` spring arrays.
Force model follows vis-network's `forceAtlas2Based` semantics — **first implementation task: pin
the exact formulas from the pinned vis-network version's solver sources
(`ForceAtlas2BasedRepulsionSolver`, `CentralGravitySolver`, `SpringSolver`,
`PhysicsEngine._performStep`) and record them in the module docstring**:

- Repulsion: FA2 linear-falloff `F = G·m_i·m_j / d`, exact O(n²) vectorized with row-chunking
  (block ≈ 512) to bound temporaries. `repulsion_fn` is an explicit seam — a Barnes-Hut/grid
  implementation for the 1500+ regime is a follow-up spec.
- Central gravity: FA2 distance-independent variant for etymology; barnesHut variant for concept.
- Springs: per-edge `F = k_e·(L_e − d)`, both endpoints; era-layered adds the invisible
  intra-family springs.
- avoidOverlap: vis's radius-adjusted distance with estimated node radius
  `clamp(12 + 3.5·label_len, 20, 60)` (the server cannot measure rendered boxes — documented
  approximation).
- Integration: `a = (F − damping·v)/m`; `v` clamped to `maxVelocity` per component; `dt = 0.5`;
  zero velocity/displacement on fixed axes.
- Convergence: `max ‖v‖ < minVelocity` (2.0 etymology / 0.75 concept) or iteration cap
  (300 force-directed / 500 era-layered / 300 concept).
- Determinism: seeded jitter for coincident points via
  `np.random.default_rng(hash(sorted node ids) ⊕ algo_version)`; two runs must be bit-identical.

Layout parameters mirror today's per-layout constants (`graph.js` `LAYOUTS` registry and
`concept-map.js` physics): force-directed `G=-350, cg=0.025, L=120, k=0.06, damping=0.5,
avoidOverlap=0.5`; era-layered `G=-80, cg=0.001, L=500, k=0.002, damping=0.95, avoidOverlap=0.7`,
Y fixed per tier, mass 1; concept barnesHut `G=-8000, cg=0.08, L=250, k=0.005, damping=0.5`.

**Budget**: cupboard (940 nodes) must solve in **< 1.5 s** — enforced by
`backend/tests/test_layout_perf.py` (`tier0` + `slow`). Estimates: 263 nodes ≈ 0.2 s; 940 ≈
1.5–3 s worst-case at full iteration budget (the good seed should roughly halve iterations).
Mitigation if missed: repulsion every 2nd iteration. 3000+ nodes ⇒ Barnes-Hut follow-up (§11).

Backend emits `family` and `tier` on layout nodes (needed server-side for era-layered anyway);
the frontend keeps its `classifyLang` copy for colors — golden (4) prevents silent drift.

## 7. R4 — Endpoints, SSE protocol, cache, nginx

New router `backend/app/routers/layout.py`, mounted in `main.py`:

| Endpoint | Purpose |
|---|---|
| `GET /api/etymology/{word}/tree/layout` | same params as `/tree` + `layout=era-layered\|force-directed`; returns `{nodes, edges, positions, meta}` (positions rounded to 1 dp; nodes carry additive `family`/`tier`). Snapshot/curl/cache-warming surface. |
| `GET /api/etymology/{word}/tree/layout/stream` | SSE; the UI's single request per search |
| `GET /api/concept-map/layout` and `…/layout/stream` | `concepts=` (comma list — server replicates app.js's multi-concept merge/dedupe), `pos`, `threshold` (similarity cutoff for the solve's edge set), `include_etymology_edges`; `graph` event includes **populated `phonetic_edges`** (all pairs ≥ floor 0.3 or Turchin, as the worker emits today) so the client filters without refetching. `/concept-map` itself unchanged. |

**SSE protocol** (`text/event-stream`; EventSource is GET-only):

```
event: graph   data: {nodes, edges, meta:{layout, algo_version, node_count, edge_count, cache:"hit"|"miss"}}
event: frame   data: {i, t_ms, positions: {"word:Lang":[x,y], …}}     # full positions, not deltas
event: final   data: frame shape + {converged, iterations, solve_ms, algo_version}   # ALWAYS emitted
event: error   data: {message}                                         # then close
: ping                                                                  # heartbeat every 15 s
```

- The **first event carries the full graph** (same node/edge shape as `/tree` + additive fields),
  so server mode makes one request — no duplicate `/tree` call. With R1 determinism, re-running
  TreeBuilder yields the identical topology `/tree` would return.
- Frame cadence: emit when `iteration % ceil(budget/12) == 0` **and** ≥ 80 ms since the last emit
  (~5–15 frames per solve); latest-wins when the client is slow. Cache hit ⇒ `graph` then `final`
  immediately, zero frames.
- Execution: topology built on the event loop (Motor); solve via `run_in_executor`, frames pushed
  through `asyncio.Queue(maxsize=2)` with `call_soon_threadsafe` (frames droppable, `final`
  never). Hand-rolled SSE formatter (~30 lines) — no new dependency. Client disconnect: poll
  `request.is_disconnected()` between reads; `finally:` sets the solver's cancellation event.
  Response headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

**Cache**: Mongo collection `layouts` (pattern: `etl/precompute_edges.py`). `_id = sha256` of the
canonical-JSON key `{kind, word|concepts, lang, types(sorted), etym, depths, layout, threshold?,
algo_version}`; doc stores `positions`, `node_ids_hash`, `solve_ms`, `created_at`. On hit,
validate `node_ids_hash` against the freshly built topology (data reloads invalidate naturally;
mismatch ⇒ miss). Write-through after solve, fire-and-forget with error logging. No TTL (dataset
static); `algo_version` bump orphans old entries — manual drop documented.

**nginx** (`frontend/nginx.conf`, `/api/` block): add `proxy_http_version 1.1;
proxy_set_header Connection ""; proxy_read_timeout 300s;`. Unbuffering is per-response via the
backend's `X-Accel-Buffering: no`, so normal endpoints keep proxy buffering. Verify:
`curl -N http://localhost:8080/api/etymology/cheese/tree/layout/stream` shows incremental frames.

## 8. R5 — Frontend integration

- **Flag** `layoutMode=server|client`: precedence URL param (registered in `router.js`) >
  `localStorage.layoutMode` > default (`client` until the final flip). `window.__layoutMode`
  exposed for E2E.
- **New `frontend/public/js/layout-stream.js`** (plain script tag):
  - `openLayoutStream(url, {onGraph, onFrame, onFinal, onError, graphTimeoutMs: 10000})` —
    EventSource wrapper; module-level singleton closed before any new request, on view switch, and
    in `destroyConceptMap`.
  - `createPositionTween(nodesDataSet)` — per `frame`: tween start = current positions, end =
    frame positions; one rAF loop issuing a single batched `nodesDataSet.update([{id,x,y}, …])`
    per tick. Linear easing between frames (the frames themselves carry the FA2 dynamics — that
    *is* the organic settle); 300 ms ease-out on `final`. Nodes being dragged are user-owned and
    skipped. Tween math extracted as pure functions for Vitest.
- **graph.js** (`updateGraph`): server mode ⇒ `options.physics.enabled = false` at construction
  (full solver options retained); **existing client seeding stays as frame-0** so first paint is
  identical to today (server seed ≈ client seed by the parity tests — no visual jump).
  `dragStart` re-enable / `dragEnd` freeze kept — physics engages from an already-stable state
  for local micro-adjustment (if drift toward the client equilibrium proves too large, server-mode
  drag switches to physics-off; decide during verification). LOD, clustering,
  `applyPerformanceOverrides`, era-band `onBeforeDrawing`, wheel/pinch, click-to-center,
  hop-opacity dimming: untouched.
- **Filters re-solve on the backend.** Every control that changes topology or layout inputs
  re-requests the solver (mirrors today's refetch-on-change at `app.js:289-311`): etymology type
  checkboxes (`types`), layout dropdown (`layout`), concept etymology-edge toggle, similarity
  slider. Each change closes the in-flight stream and opens a new one (server cancels the orphaned
  solve); cache keys cover all params, so returning to a previously seen combination is a warm hit.
- **Position continuity across filter changes**: capture `network.getPositions()` before rebuild;
  surviving node ids start at their previous coordinates (only new nodes get seed positions).
  Since tweens start from current positions, filter toggles morph the layout instead of
  restarting it.
- **concept-map.js**: server mode ⇒ no Worker spawn; `phonetic_edges` arrive once via `graph`.
  The slider filters edges client-side **during drag** (instant); **on release (debounced
  ~300 ms) it re-requests a solve with the new `threshold`** — streamed frames tween from current
  positions, replacing today's local `stabilize(100)`. Worker path kept verbatim for client mode.
- **Fallback**: `onError` or no `graph` event within 10 s ⇒ close the stream and run today's
  exact path (`getEtymologyTree` + client physics). One shared code path selected by flag or
  fallback.
- **index.html**: pin `vis-network` to the exact version unpkg currently resolves (optionally
  vendor into `frontend/public/vendor/` to remove CDN flake from E2E); add the
  `layout-stream.js` script tag.

## 9. R6 — Test & docs migration

- `frontend/tests/graph-perf.test.js`: existing assertions survive (they govern client/fallback
  mode). Add: server-mode option construction (`physics.enabled === false`), tween math, frame
  application over a fake `{update}` DataSet.
- E2E: SPC-00004's R1–R4 assertions survive as-is. Force `?layoutMode=client` on R5
  (stabilized→freeze) and R7 (barnesHut > 1000) so they keep testing the fallback architecture.
  New `tests/e2e/server-layout.spec.js` (`?layoutMode=server`): physics disabled from
  construction; final positions applied (via a `window.__lastLayoutFinal` hook set by
  layout-stream.js); generous time-to-final ceiling (< 6 s in CI — the real target lives in the
  baseline harness, not flaky CI); fallback engages when `**/layout/stream` is blocked via
  `page.route`; concept map has phonetic edges without a Worker and slider changes re-request
  without enabling physics. Extend `tests/e2e/helpers.js` with `waitForFinalFrame(page)`.
- Backend: Tier 0 — SSE formatter, cadence policy, cache-key canonicalization, all §6 parity and
  invariant tests (fixed nodes immobile; era Y invariant; bit-identical reruns). Tier 2 — engine
  frame-iterator ordering, cancellation, cache-hit path over the `FakeWordsCollection`.
  Acceptance — `httpx.ASGITransport` + `dependency_overrides` seeded from fixture docs: event
  ordering/schema, `final.positions ==` plain-GET positions, unknown word ⇒ orphan node not 500.
  Live characterization — `tests/integration/test_layout_characterization.py`: node-id sets exact,
  positions `atol=0.5 px` (cross-machine float tolerance), `algo_version` exact; snapshots under
  `tests/fixtures/layout/final/`.
- Docs (**before** the feature commits, per CLAUDE.md): `docs/FEATURES.md` "Server-side layout &
  streaming" section (endpoints, event schema, flag, cache, fallback, known limitations:
  overlap-radius approximation, slider re-solve round trip); CLAUDE.md Current Status + vis.js
  section; audit addendum (R3 fixed by this spec's Phase 0).

## 10. Implementation phases & acceptance

Ordered commit groups (each green + revertible), branch `claude/visjs-graph-performance-hlr7q6`:

1. **Phase 0a+0e**: this spec + decision log; R1 determinism fix + fixture regen.
2. **Phase 0b–0d**: JS goldens; `FakeWordsCollection` + real TreeBuilder tests + markers;
   baseline harness (numbers recorded below). *Parallelizable with 3.*
3. **Phase 0e DI**: SPC-00020 Steps 1–3 + `httpx` dev dep.
4. **Phase 1**: layout engine + numpy + parity/perf tests (pure; no endpoints).
5. **Phase 2**: endpoints + SSE + cache + nginx + acceptance/characterization tests.
6. **Phase 3+4**: frontend integration (default `client`) + E2E + docs.
7. **Phase 5**: flip default to `server`; before/after table below.

**Baseline (Phase 0d, measured 2026-07-10):**

| Graph | Nodes | Baseline settle (client physics) | Server cold | Server warm |
|---|---|---|---|---|
| cheese | 108 | force-directed 11.65 s; era-layered never stabilizes¹ | | |
| fire | 271 | force-directed 25.37 s; era-layered never stabilizes¹ | target < 1.2 s | |
| hound | 326 | force-directed 15.26 s; era-layered never stabilizes¹ | | |
| wine | 534 | force-directed 72.83 s; era-layered never stabilizes¹ | | |
| cupboard | 779 | force-directed 143.16 s; era-layered never stabilizes¹ | target < 2.5 s | target < 0.8 s |

Measurement conditions: `make bench-layout-baseline` (Apple M2, macOS 26.5, headless Chromium /
Playwright 1.58), median of 3 runs; metric per §5 (`stabilized` event − network creation). Run
variance was < 0.2% throughout (fixed `randomSeed` ⇒ deterministic tick count). Long-frame
(> 33 ms) counts during settle were 0–2 up to wine and 9 for cupboard — on this hardware the cost
shows up as total settle duration rather than per-frame jank. Node counts are the post-R1
regenerated fixture trees (PRs #14/#15); the pre-R1 estimates (fire 263, hound 464, wine 540,
cupboard 940) predate the determinism + reverse-edge fixes. Trees were served from the SPC-00013
captures (`LAYOUT_BASELINE_FIXTURES=1` — topology identical to the live API; the measured window
starts after the response is parsed) because the local dataset was lost at measurement time; the
concept-map baseline requires the live DB and is deferred until after a data reload (see the
decision-log addendum). The wine/cupboard force-directed medians exceed the harness's default
90 s settle ceiling — reproducing them requires the documented override, e.g.
`LAYOUT_BASELINE_TIMEOUT_MS=240000 LAYOUT_BASELINE_LAYOUTS=force-directed make bench-layout-baseline`
(the ceiling only bounds the wait; it does not affect the measured settle time).

¹ era-layered produced no `stabilized` event on any word (90 s ceiling): same-tier nodes on a
fixed-Y band shove each other via `avoidOverlap` with velocities riding the `maxVelocity` clamp
(73–100% of frames; unchanged after 3+ min). §11 risk 2 is today's production behavior — the
SPC-00004 R5 physics freeze never engages for the default layout, so client physics burns CPU
indefinitely. The server engine's era-layered iteration cap (§6) is what first gives this layout
a bounded settle at all.

**Acceptance** ("settled" := today's `stabilized` event; server := `final` applied + tween done):
targets above; no > 16 ms main-thread frames during server-mode settle; first paint not slower
than today; era bands / family cluster ordering / root-at-origin visually equivalent (side-by-side
screenshots in `docs/screenshots/`); all existing E2E green under `?layoutMode=client`;
`curl -N` shows incremental frames through nginx.

**Rollback**: flag default is a 1-line revert; endpoints are additive; `/tree`/`/concept-map`
byte-identical; `layouts` collection droppable; solver changes ship as `algo_version` bumps.

## 11. Risks & out of scope

**Risks**
1. *FA2 parity*: final layouts will differ somewhat from vis.js despite same constants and seed —
   acceptance is visual equivalence, not positional equality. Formulas pinned from vis source.
2. *Era-layered 1D solve* (fixed Y + invisible springs) can oscillate; damping 0.95 should
   overdamp — fallback is a smaller `dt` for era-layered only.
3. *940-node solve budget* is the tightest estimate; mitigations: seed quality, every-2nd-iteration
   repulsion.
4. *Fixture diffs from R1* (alphabetical bias under the 50-cap) need human review.
5. *Slider/filter re-solve round trips*: mitigated by debounce-on-release, `threshold` in the
   cache key, and small per-threshold solves; client-side-filter-only remains a one-line fallback.
6. *dragStart re-enable drift* over a server-solved layout: decide physics-off drag during
   verification if the nudge is too big.

**Out of scope (deferred)**
- Barnes-Hut / grid repulsion for the 1500–3000+ regime (follow-up spec behind the `repulsion_fn`
  seam).
- ML-predicted layouts (experimental; would need training data, serving, and a quality oracle —
  revisit once deterministic layouts + the cache provide a corpus).
- SPC-00020 Step 4 (repository port) and full tier rollout beyond the groundwork here.
- SPC-00014's out-degree descendant ranking and native-`descendants` sourcing.
- Precompute ETL for popular words (`etl/precompute_layouts.py`) — the cache makes it a trivial
  follow-up if wanted.
