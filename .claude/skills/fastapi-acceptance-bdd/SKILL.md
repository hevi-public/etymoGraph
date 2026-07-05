---
name: fastapi-acceptance-bdd
description: Wiring hermetic, HTTP-level acceptance tests for the Etymology Explorer FastAPI backend, plus the Playwright E2E layer above it. Use this whenever adding or fixing acceptance tests — in-process httpx.ASGITransport clients, dependency_overrides at the Mongo seam, seeding FakeWordsCollection from SPC-00013 fixtures, per-test state isolation and autouse cache resets, parametrized failure modes, SSE stream-contract tests, config-guardrail "rail" tests, or the live characterization suite in tests/integration. Reach for it before touching backend/tests acceptance code, tests/integration, or tests/e2e wiring.
---

# Hermetic acceptance testing for Etymology Explorer (FastAPI + httpx + Playwright)

Adapted from the HAIP project's `cucumber-spring-bdd` skill (hevi-public/haip). HAIP drives its
acceptance tier through Cucumber-JVM over Spring; this stack keeps the **discipline** — HTTP-level
scenarios, one app context, one scriptable fake at the IO seam, per-scenario isolation — without
adopting Gherkin. Plain pytest with scenario-style test names does the same job with less
machinery. This is the acceptance tier of [[bdd-tiered-testing]]; read that first for the
philosophy.

Two suites exist above Tier 2, with different trust properties:

| Suite | Transport | Stack needed | Trust |
|---|---|---|---|
| **Hermetic acceptance** (`acceptance` marker) | `httpx.ASGITransport` — in-process, no server | none | what CI relies on |
| **Live characterization** (`tests/integration/`, `live`) | real HTTP via `make run` | full Docker + loaded data | opt-in; **skips-as-pass when the stack is down** (`conftest.py` pings `/health`) — never treat its green as coverage |
| **E2E** (`tests/e2e/`) | Playwright browser | full Docker + loaded data | UX truth, slowest |

## The in-process client (no live server, no port)

Requires `httpx` in `backend/requirements-dev.txt` and the SPC-00020 Steps 1–3 DI seam (lifespan
client + `Depends` providers) — both land with SPC-00021 Phase 0.

```python
import httpx
from app.main import app
from app.database import get_words_collection

async def make_client(fake_col) -> httpx.AsyncClient:
    app.dependency_overrides[get_words_collection] = lambda: fake_col
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")
```

Rules:

- **Override at the seam only** — `get_words_collection` (later, the repository provider). Never
  patch a service or router internal; that hides the integration under test.
- **Clear overrides after every test** (`app.dependency_overrides.clear()` in a fixture
  `finally`). A leaked override is cross-test state.
- `pytest-asyncio` runs with `asyncio_mode = "auto"` (`pyproject.toml`) — plain `async def` tests
  work; keep fixture loop scope at function level so Motor/loop binding never bites.

## Seeding: SPC-00013 fixtures are the acceptance corpus

`tests/fixtures/wiktionary/*.json` each carry the input docs (`query`) and the captured API
outputs (`system_output.{chain, tree_inh, tree_inh_bor_der_cog, word_detail}`) for 11 curated
words. The hermetic suite seeds `FakeWordsCollection` from the input docs and asserts the app
returns `system_output` — the same expectations the live suite checks over HTTP, now CI-runnable.
Regenerate fixtures only deliberately (`make collect-fixtures` against a running stack) and review
the diff like code; they are frozen baselines, not correctness oracles.

## Per-scenario state: fixtures, never module globals

The HAIP trap ("state on step classes leaks across scenarios") translates directly:

- Build a **fresh `FakeWordsCollection` per test** via a fixture; never share a seeded fake at
  module scope.
- Two module-global caches leak across tests by design: `lang_cache._code_to_name/_name_to_code`
  and `concept_resolver._concept_cache`. An **autouse fixture resets both before every test** —
  without it the suite is order-dependent (SPC-00020's explicit decision: keep the globals, reset
  them honestly).
- Anything a test creates through the API (e.g. cache writes to the `layouts` collection fake)
  dies with the per-test fake — that's the point.

## The scriptable fake: behaviours + a spy

The single fake at the seam does two jobs, exactly like HAIP's `ScriptableLlmClient`: return
scripted data/failures, and **record what it received** so tests can assert on inputs, not just
outputs.

`backend/tests/fakes.py::FakeWordsCollection` (SPC-00021 Phase 0) implements only the surface the
services touch — `find_one`, `find(...)` → cursor with `.sort/.limit/.to_list`/`async for`, the
`$elemMatch` matcher for `name.$in`/`args.2`/`args.3`, and the `.database["etymology_edges"]` hop.
Extend it with:

- `queries: list[dict]` — a spy of every filter it was asked, for assertions like "changing only
  the layout param must not re-query descendants."
- `fail_next(exc)` — scripted failure injection at the IO boundary (the persistence-failure
  analog; never simulate failure by mocking a service).

Every fake behaviour needs a **paired Tier-1 contract test** against real Mongo ([[mongodb-motor-data]])
— an unanchored fake can return anything and hide a query bug.

## Parametrized failure modes

HAIP's custom `@ParameterType` for failure words maps to plain `pytest.mark.parametrize`:

```python
@pytest.mark.acceptance
@pytest.mark.parametrize("word,expect", [
    ("nosuchword",  "single orphan node, HTTP 200"),   # unknown word is NOT a 500
    ("Fóo",         "normalize_word fallback fires"),
    ("cyclic-seed", "cognate expansion terminates at round cap"),
])
async def test_tree_error_scenarios(word, expect, client): ...
```

Assert the **user-visible outcome and the state transition**, not internals. For SSE (below), the
failure contract is: `error` event with a message, then stream close — never a hung stream, never
an unhandled exception in the executor.

## SSE stream-contract tests (SPC-00021)

`httpx.AsyncClient.stream("GET", ".../tree/layout/stream")` consumes SSE in-process. Assert the
protocol, not timing:

- Event order: `graph` first (full nodes/edges + meta), zero-or-more `frame`, exactly one `final`
  (also on cache hit — then with zero frames), or `error` terminal.
- `final.positions == ` the plain `GET .../tree/layout` positions for the same params.
- Disconnect mid-stream → the solver's cancellation event is set (assert via the engine's hook).
- Read events with a generous `asyncio.wait_for` as a **failsafe only** — never sleep-and-poll
  ([[bdd-tiered-testing]] § de-flake).

## Rail tests: config guardrails are behaviour

Config drifts silently, so assert the wiring itself (HAIP's "rail scenarios"):

- Under tests, the Motor client must point at a **test database** (`etymology_test` /
  testcontainers URI), never the real `etymology` DB with its 10.4M docs — assert the resolved
  `settings.mongo_uri`/client target in a `tier1` rail test.
- The hermetic acceptance suite must **fail loudly, not skip**, if `httpx` is missing (mirror the
  `requires_docker` gate).
- The live suite keeps its skip-when-down behaviour, but that suite is `live`-marked and opt-in —
  a CI job must never count it as coverage.

## The Playwright layer on top

`tests/e2e/` (config: `playwright.config.js`, baseURL `localhost:8080`, chromium) is the browser
tier. Conventions:

- Assert on **stable hooks**, not visuals: `window.__etymoNetwork`, `window.__etymoNodesDS`, and
  (SPC-00021) `window.__layoutMode` / `window.__lastLayoutFinal` — the inventory lives in
  [[vanilla-js-frontend]]. Shared helpers in `tests/e2e/helpers.js` (`waitForGraph`,
  `zoomToScale`; SPC-00021 adds `waitForFinalFrame`).
- Never gate a test on data-dependent `test.skip(nodeCount <= N)` without a loud reason — that
  pattern made `large-graph-perf.spec.js` silently no-op on small DBs. Prefer deterministic seeded
  inputs (fixture words with known sizes: cheese 108 … cupboard 940 nodes).
- Route-blocking (`page.route("**/layout/stream", abort)`) is the E2E analog of `fail_next` —
  force the fault at the real boundary to prove the fallback path, mock nothing internal.
- Pin architecture modes explicitly per spec file: `?layoutMode=client` for tests asserting the
  legacy physics path, `?layoutMode=server` for the streaming path.

## Common failure points

- **Overrides not cleared** → later tests hit the fake of an earlier one. Clear in fixture teardown.
- **Motor loop binding** → a client created at import time binds the wrong event loop under
  pytest-asyncio; keep client creation in `lifespan` (SPC-00020 Step 1) and let overrides bypass
  it entirely in hermetic tests.
- **Cache contamination** → intermittent failures that depend on test order = a missing autouse
  reset of `lang_cache`/`_concept_cache`.
- **Green-but-empty runs** → `pytest -m acceptance` collecting zero tests, or the live suite
  skipping on a down stack. Check collection counts in CI; zero collected in a capable environment
  is a failure.
- **Asserting snapshot bytes on the layout endpoints** → positions compare with `atol=0.5px`
  (cross-machine float tolerance); only node/edge *sets* and `algo_version` compare exactly
  (SPC-00021 §9).

## Verify the wiring

`pytest -m acceptance` boots no server, runs against the seeded fake, and fails RED for the right
reason on a missing endpoint (404 — not an import error). `make test-integration` with the stack
up replays the same fixture expectations over real HTTP. `make test-e2e` drives the browser. All
three green = the contract holds at every altitude.
