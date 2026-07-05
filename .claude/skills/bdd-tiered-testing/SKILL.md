---
name: bdd-tiered-testing
description: Etymology Explorer's BDD/TDD testing philosophy and tiered test architecture. Use this whenever writing or organizing tests in this Python/FastAPI/Motor + vanilla-JS codebase — deciding what to fake, which tier a test belongs to (Tier 0/1/2/acceptance/live/E2E), keeping the single Mongo seam injectable, adding pytest markers or Make targets, using discovery mode for red-first specs, or covering error scenarios. Consult it before adding any new test so the suite stays a trustworthy executable spec and the "fake only at one seam" guarantee holds.
---

# BDD/TDD tiered testing for Etymology Explorer

Adapted from the HAIP project's `bdd-tiered-testing` skill (hevi-public/haip, a Kotlin/Spring stack)
for this Python/FastAPI/Motor/vanilla-JS stack. The architecture half of that philosophy is specced
in depth as **SPC-00020 (Tiered Testing Architecture)** — read it for the seam design and refactor
staging; this skill is the working discipline, including practices SPC-00020 doesn't cover.

The suite is the primary control layer against agent drift and the executable spec the project
builds behind — so it must stay honest. Honesty means two things: a failing test means real
behaviour broke (not a brittle mock), and the place a test lives tells you what it actually
exercises. The historical failure mode here is the opposite and it is *documented*: the
`tests/integration` suite skips-as-pass when the stack is down, and `test_tree_builder.py` shipped
async tests that passed vacuously (no assertions). **Green must mean "nothing broke," never
"nothing ran."**

## The one load-bearing rule: fake only at the IO seam

There is exactly **one** seam where we substitute fakes: the Mongo IO boundary (today the Motor
collection handed to services; after SPC-00020 Step 4, the `WordsRepository` port). Everything
above it runs **real** code against that single fake. If you find yourself mocking a service to
test a router, or `monkeypatch`ing an internal method of `TreeBuilder`, stop — that hides the very
integration the test exists to prove.

Why this matters: a suite that mocks internally can stay green while the wired-together system is
broken. With fakes allowed only at the IO edge, a green higher-tier test means the real parsing +
tree building + router logic actually compose.

## The tiers (this stack)

| Tier | What it tests | Fakes | Marker | Examples |
|------|---------------|-------|--------|----------|
| **Tier 0** | Pure logic, no IO | none | `tier0` | `template_parser.extract_ancestry`/`node_id`, `etymology_classifier`, `phonetic_similarity.build_similarity_edges`, `TreeBuilder.add_node/add_edge/result`, the SPC-00021 layout engine (`services/layout/`: seed parity vs goldens, solver invariants); JS pure core via the Vitest eval harness (`router.js` parse/build, `graph.js` position/perf helpers) |
| **Tier 1** | The IO boundary itself | nothing above it; this *is* the seam — **real ephemeral Mongo** | `tier1` | the real query strings: `find_descendants`'s dotted `$elemMatch`, `suggest_concepts` collation (collation is Tier-1-**only** — mongomock silently ignores it), `_expand_polysemous` `$arrayElemAt`, the `etymology_edges`/`languages` sibling-collection hops |
| **Tier 2** | Orchestration | the single fake collection/repo | `tier2` | `TreeBuilder.expand_word`/`find_descendants` guard logic/`expand_cognates` round+cycle caps over `backend/tests/fakes.py::FakeWordsCollection`; routers via `app.dependency_overrides` |
| **Acceptance** | Full FastAPI app in-process | only the Mongo seam, seeded | `acceptance` | `httpx.ASGITransport` against the real app; SPC-00013 fixtures replayed hermetically; SSE stream contract (SPC-00021) — see [[fastapi-acceptance-bdd]] |
| **Live** | Same assertions over the running Docker stack | none | `live` | `make test-integration` — the SPC-00013 characterization suite. Opt-in; its skip-when-down behaviour is acceptable *only* because the hermetic acceptance tier is the one CI relies on |
| **E2E** | Browser over the full stack | none | Playwright | `tests/e2e/*.spec.js` via `make test-e2e` |

Run order is **lowest-first** (`make test` should chain tier0 → tier1 → tier2 → acceptance). A
break low down ripples upward, so the lowest failing tier names the culprit — read it first and
ignore the cascade above it.

Build order is the **opposite** (outside-in, top-down): write the acceptance test for the endpoint
contract first (RED — a 404 or a failing schema assertion, not an import error), bring the router
up against the seeded fake, then fill in services and queries behind the now-frozen contract.
Writing tests first pins the contract before any logic exists. SPC-00021's golden-fixture step is
this same move for a *port*: characterize the JS layout functions before writing the Python twin,
so the contract exists before the code.

## Injectable dependencies are the discipline that keeps the seam intact

The "one fake" guarantee only holds if the boundary is *injectable*. The Python failure modes to
watch for mid-stack:

- `AsyncIOMotorClient(...)` built at **import time** (`database.py` today — SPC-00020 Steps 1–3
  move it into a FastAPI `lifespan` and expose `Depends` providers; until then, services must keep
  taking `col` via constructor, which `TreeBuilder` already does).
- `datetime.now()` / `time.time()` mid-logic — pass timestamps in, or inject a clock.
- `random` without a seed — the SPC-00021 solver derives its RNG seed from the node-id set +
  `algo_version` precisely so runs are bit-identical.
- Module-global caches read inside logic (`lang_cache`, `concept_resolver._concept_cache`) — these
  stay globals by explicit SPC-00020 decision, but every test run resets them via an **autouse
  fixture**; never let a test depend on their prior state.

On the JS side the same rule reads: pure cores never touch `Date.now()`, `localStorage`, or the
DOM directly — see [[vanilla-js-frontend]] for the pure-core/DOM-glue split.

## Testing the production adapter — the real code that IS the seam

Code above the seam is tested against the fake; but the real adapter (the Motor query methods
today; `MongoWordsRepository` after the port) is real code too. Split it so the un-fakeable part
shrinks to almost nothing:

1. **Pure result→domain classification → Tier 0.** Anything that interprets a raw document — 
   `extract_ancestry` over `etymology_templates`, uncertainty classification, `format_word_for_response`
   — is a pure function fed a captured dict. Feed it canned fixture docs (the SPC-00013
   `tests/fixtures/wiktionary/*.json` files carry real ones).
2. **The irreducible IO → Tier 1 against a real ephemeral Mongo** (testcontainers-python or a
   throwaway `etymology_test` DB). This is where the actual query strings — `$elemMatch` with
   dotted `args.2`/`args.3`, sort-before-limit, collation — are proven. A hand-rolled fake that
   never has its behaviour cross-checked at Tier 1 can return anything and hide a query bug:
   **every `FakeWordsCollection` behaviour gets a paired Tier-1 contract test.**

The same split shows up in the frontend↔backend pair: `similarity-worker.js` and
`phonetic_similarity.py` implement the same math, and the pure Python version is the **oracle**
the vectorized `phonetic_numpy` twin is exact-equality-tested against (SPC-00021).

## Error scenarios are first-class

Every failure mode gets explicit coverage, at the lowest tier that can express it (the list lives
in SPC-00020 §"First-class error scenarios"): unknown word → single orphan node, not a 500;
normalization fallback fires only when `normalized != raw`; malformed/named-arg/empty templates
skipped, not crashed; the descendant cap asserted as *membership + count*, pinned to identity only
now that the deterministic sort exists; cognate cycle/round bounds terminate; SSE `error` event on
failure mid-stream, `final` always emitted otherwise (SPC-00021). Assert the **state/outcome the
user sees**, and assert *absence* too — e.g. no LLM-analog here, but the same idea: a filter
change must *not* refetch when the flag says client mode.

## De-flake via events, not wall-clock polling

Never await an async settle by sleeping and sampling. Use an event the code under test already
emits, and make any timeout a **failsafe, never a sampling interval**:

- asyncio: `await queue.get()` / `asyncio.Event` with a generous `asyncio.wait_for` bound — e.g.
  SSE tests read events off the stream until `final`, with the timeout only guarding a hang.
- Playwright: `await expect(...).toPass()` / `waitForFunction` on a real signal
  (`window.__etymoNetwork` set, `stabilized` fired, `__lastLayoutFinal` present — see
  [[vanilla-js-frontend]] for the hook inventory), never `page.waitForTimeout` as a sync point.
- The known anti-pattern to hunt down: `tests/e2e/large-graph-perf.spec.js`'s
  `test.skip(nodeCount <= N)` silently no-ops on a small DB. Prefer a deterministic seeded corpus;
  where a skip is unavoidable, make it *loud* (a logged skip reason counted in review).

## Logging is IO — assert it

A log line an operator (or a dashboard) reads is an output surface, same as a JSON body. Below the
seam everything is faked, so log output is deterministic — assert it with pytest's `caplog`, and
assert the **level + message**, never the formatted layout:

```python
def test_cache_miss_logs_event(caplog):
    with caplog.at_level(logging.INFO, logger="app.routers.layout"):
        ...
    rec = next(r for r in caplog.records if getattr(r, "event", "") == "layout.cache.miss")
    assert rec.levelno == logging.INFO
```

Conventions that make this a durable contract (adopt for all *new* operational logging — the
backend currently logs very little, so the bar applies going forward, e.g. SPC-00021's layout
solver and cache):

- **Structured event ids over prose.** Emit a namespaced dotted constant via `extra=`:
  `logger.info("layout cache miss for %s", key, extra={"event": "layout.cache.miss", "word": word})`.
  Reword the human message freely; treat an `event` id or field-key change as a breaking change to
  log consumers, and update its test deliberately.
- **Pin the logger name** (`logging.getLogger(__name__)` at module top — stable, greppable).
- **Silence is behaviour too**: assert a best-effort path (cache write-through failure) logs at
  WARN once and does *not* raise.

## Build-breaks-on-red, with an opt-in discovery mode

Default stance: a failing test fails the run (`pytest` exits nonzero; that is what makes the suite
a control layer). While scaffolding red-first specs, mark them instead of loosening the build:

```python
@pytest.mark.discovery          # xfail(strict=False) via marker config — red doesn't break the build
def test_descendant_cap_ranks_by_out_degree(): ...
```

Remove the marker the moment it goes green, making it build-breaking. `make discover` runs
`pytest -m discovery --runxfail || true` to see the red list. This is how a spec's assertions can
exist *before* their implementation (SPC-00020 uses it for SPC-00014's out-degree cap).

## Markers and Make targets (tiered run)

Markers `tier0 tier1 tier2 acceptance live discovery` are registered in `pyproject.toml`
`[tool.pytest.ini_options]` so an unknown marker errors (registration lands with SPC-00021
Phase 0). Frontend: `make test-frontend` (Vitest, no stack). Browser: `make test-e2e` (needs
`make run`). Live characterization: `make test-integration` (needs `make run`; skips loudly
otherwise). Tier 1 must **skip loudly** without Docker, and CI should fail if Tier 1 collected
zero items in an environment that has Docker — collation/`$elemMatch` coverage must not silently
vanish.

## Tests double as documentation

A function's behaviour is defined by its tests, so write them to read as behavioural descriptions:
scenario-style names (`test_tree_falls_back_to_mentions_when_no_ancestry`), arrange-act-assert,
one behaviour per test. A future reader — human or agent — consults the test to learn what the
code does; make it worth reading.

## Where to go next

- Hermetic acceptance + SSE contract wiring, fakes with spies, rail tests → [[fastapi-acceptance-bdd]]
- The Mongo seam, real-test-DB strategy, query gotchas, bounded recursion → [[mongodb-motor-data]]
- Frontend pure-core split, Vitest eval harness, stable E2E hooks → [[vanilla-js-frontend]]
- The seam architecture and staged DI refactor in full → `specs/00020-tiered-testing-architecture/spec.md`
- What this net exists to protect right now → `specs/00021-server-side-layout-streaming/spec.md`
