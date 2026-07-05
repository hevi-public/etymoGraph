---
name: vanilla-js-frontend
description: Conventions for the Etymology Explorer frontend — no-build-step vanilla JS served by nginx, vis.js networks, script-tag load order and shared global scope, the pure-core/DOM-glue split that keeps logic Vitest-testable, the eval-the-source test harness, stable test hooks (window.__etymo* globals and DOM ids), localStorage keys, CDN pinning/vendoring, and SSE/Web-Worker consumption patterns. Use this whenever creating or editing files under frontend/public/js, adding a script tag, deciding where logic vs DOM code lives, exposing state for E2E tests, or debugging "works in browser, untestable in Vitest".
---

# Vanilla-JS frontend for Etymology Explorer

Adapted from the HAIP project's `jte-spring-kotlin` skill (hevi-public/haip). HAIP's stack is
server-rendered JTE + htmx; almost none of that machinery exists here — nginx serves static files
from `frontend/public/`, FastAPI serves JSON, and the UI is hand-written vanilla JS + vis.js with
**no build step, no bundler, no framework**. What survives the translation is HAIP's *discipline*:
a pure logic core split from DOM glue, stable semantic hooks the tests assert against, pinned
hermetic assets, and error signaling by status code rather than prose. This is the view layer the
acceptance/E2E tiers of [[bdd-tiered-testing]] assert against.

## Architecture: script tags share one global scope

`index.html` loads scripts in dependency order; there are no ES modules in the page (the sole
`.mjs`-style unit is the Web Worker, which is its own scope). Every file's top-level `function`s
and `const`s are effectively globals shared by later scripts:

| File | Role | Depends on |
|---|---|---|
| `js/api.js` | fetch client, `API_BASE = "/api"` | — |
| `js/router.js` | URL/History param registry (IIFE, exposes `router`) | — |
| `js/graph.js` | etymology vis.Network, layout seeding, interaction, detail panel | api |
| `js/concept-map.js` | second vis.Network for the concept map | api, shares graph.js helpers (`computeTreePositions`, `getTouchDistance/Center`) |
| `js/search.js` | autocomplete | api |
| `js/app.js` | orchestration: filter wiring, view switching, router glue | all of the above |
| `js/similarity-worker.js` | Web Worker: O(n²) phonetic similarity off the main thread | standalone |
| `js/layout-stream.js` (SPC-00021) | EventSource wrapper + position tween | vis DataSets |

Consequences of the shared scope:

- **Load order is a contract.** A new file that defines helpers used by `app.js` must be included
  *before* it in `index.html`.
- **Name collisions are silent.** Prefer one exported object or a distinctive prefix per file when
  adding globals.
- Duplicated logic between `graph.js` and `concept-map.js` is a known debt (deprecated SPC-00007
  proposed extracting shared graph utilities — the idea is still valid; fold extractions in
  opportunistically when touching both).

## The pure-core / DOM-glue split (the load-bearing rule)

HAIP splits `htmx-error-core.mjs` (pure store + `ageLabel`, injectable `now`/storage) from
`htmx-error.js` (DOM glue). The same split is what makes this codebase testable without a browser:

- **Pure core**: plain functions over data — `computeTreePositions`, `computeRadialPositions`,
  `applyBarycentricRefinement`, `classifyLang`, `applyPerformanceOverrides`,
  `computeHopDistances`, router `parseURL`/`buildURL`, the SPC-00021 tween math. No `document`,
  no `network`, no `Date.now()`, no `localStorage`, no `Math.random()` — inject a `now`, a seed,
  or a storage object if one is needed.
- **DOM glue**: `updateGraph`, event handlers, panel rendering — thin, and *calling* the core
  rather than containing logic.

If a function is hard to test in Vitest, that is the signal it has DOM/IO mixed into logic —
split it, don't reach for a browser test. The Worker is the precedent: `similarity-worker.js` is
pure math behind `onmessage`, and its Python twin `phonetic_similarity.build_similarity_edges`
is the cross-language oracle (SPC-00021).

## The Vitest eval-the-source harness

There is no module system to import from, so unit tests (`frontend/tests/*.test.js`, jsdom
environment per `vitest.config.js`) **read the source file and `eval` it**, then call the
now-global functions — see `graph-perf.test.js` and `router.test.js` for the pattern. Rules that
keep a file harness-compatible:

- Logic lives in **top-level `function` declarations** (hoisted, eval-visible), not inside DOM
  event handlers or `DOMContentLoaded` closures.
- Top-level code must not *touch* the DOM on load beyond `getElementById` grabs that tolerate
  `null` under jsdom (guard side effects; construction happens in functions).
- Golden-fixture tests (SPC-00021 `layout-goldens.test.js`) may write files: Vitest runs in Node,
  so `node:fs` works — regeneration is gated behind `UPDATE_LAYOUT_GOLDENS=1`, normal runs only
  assert. Goldens live repo-root in `tests/fixtures/layout/` so pytest reads the same files.

Run with `make test-frontend` — no Docker, no stack.

## Stable test hooks (this stack's `data-*` convention)

HAIP's rule — E2E asserts on stable behavioural hooks, never on CSS classes — holds here; the
inventory differs:

| Hook | Set by | Meaning |
|---|---|---|
| `window.__etymoNetwork` | graph.js on construction | the live vis.Network (E2E reads physics state, positions, scale) |
| `window.__etymoNodesDS` | graph.js | the nodes DataSet |
| `window.conceptNetwork` | concept-map.js | the concept-map network |
| `window.__layoutMode` (SPC-00021) | app.js | resolved `server`/`client` flag |
| `window.__lastLayoutFinal` (SPC-00021) | layout-stream.js | last applied `final` frame, for position assertions |
| DOM ids: `#ety-filters`, `#layout-select`, search/panel ids | index.html | interaction targets for Playwright |

Rules: treat these as a **public API for tests** — renaming or dropping one is a breaking change
that must update `tests/e2e/` in the same commit. When adding markup state that E2E must see,
prefer a `data-*` attribute on the owning element over a CSS class (classes churn with styling).
Style with `class=`, assert with `data-*`/ids/globals.

## localStorage keys

Best-effort persistence, never load-bearing (a throwing `setItem` must not break the app):

- `graphLayout` — selected etymology layout (`era-layered` default / `force-directed`).
- `layoutMode` (SPC-00021) — `server`/`client`; URL param takes precedence (registered in
  `router.js`'s view-scoped param registry — every user-facing state that should survive
  reload/share goes through that registry, not ad-hoc URL reads).

## Third-party assets: pinned or vendored, never floating

The historical bug this rule exists for: `index.html` loaded
`https://unpkg.com/vis-network/standalone/umd/vis-network.min.js` **unpinned** — any upstream
release could change rendering or APIs under us, and no lockfile records what production actually
runs. HAIP's equivalent rule is webjars ("hermetic, version-pinned like everything else").

- Pin the exact version in the URL (`vis-network@<x.y.z>`), or better, vendor the file into
  `frontend/public/vendor/` (removes CDN flake from E2E entirely). SPC-00021 Phase 3 does this.
- Any API you rely on must exist in the pinned version — check against the `vis-docs` skill
  (in-repo vis.js Network/DataSet reference) before using something new.
- New third-party scripts follow the same rule, plus SRI (`integrity=`) when staying on a CDN.

## Async consumption patterns

- **Web Worker** (`similarity-worker.js`): heavy CPU work off the main thread; messages in, edges
  out, progressive batches. Keep workers pure-math; the page-side glue owns DataSet updates.
- **EventSource / SSE** (SPC-00021 `layout-stream.js`): one module-level singleton stream, closed
  before opening a new one, on view switch, and on teardown — leaked EventSources reconnect
  forever. Handle the four events (`graph`/`frame`/`final`/`error`); a missing `graph` within a
  timeout triggers the client-physics fallback path. Frames are absolute full-position maps —
  application must be idempotent and drop-tolerant (latest wins).
- **Errors surface by status/signal, not prose parsing**: `api.js` throws on `!res.ok`; UI copy is
  worded client-side from the status — never scrape backend error strings into logic (HAIP's
  "keep human prose out of headers/signals" rule, generalized).

## Common failure points

- New helper defined after its consumer in `index.html` → `ReferenceError` only at runtime.
- Logic buried in an event handler → untestable in Vitest; extract a pure function.
- `Date.now()`/`Math.random()` inside layout/tween math → nondeterministic tests and unreproducible
  layouts; inject.
- Asserting node *positions* byte-exactly in E2E → float/tween tolerance needed; assert against
  `window.__lastLayoutFinal` with an epsilon.
- Forgetting `network.destroy()` before rebuild, or re-attaching container-level listeners inside
  `updateGraph` → listener/memory accumulation (wheel/touch handlers attach **once**, outside the
  rebuild path — keep it that way).

## Verify

`make test-frontend` green without a stack; `make run` + `make test-e2e` green in the browser;
for rendering changes, capture before/after screenshots into `docs/screenshots/` (Playwright MCP —
never `~/Downloads`) and compare side by side.
