# SPC-00020: Tiered Testing Architecture

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | SPC-00013 (recharacterizes the integration suite as a hermetic Acceptance tier), SPC-00014 (supersedes its ad-hoc §5 test plan with the shared tier model) |
| **Modified-by** | — |

> Adapts the **`bdd-tiered-testing`** philosophy (a Kotlin/Spring skill) to this Python/FastAPI/Motor/JS
> stack. Its load-bearing rule — **mock at exactly one seam, the IO boundary; run real code above it** —
> directly addresses the [2026-06 audit](../../docs/AUDIT-2026-06.md#a3--correctness--test-gaps)'s top
> correctness risk (R2). The design below was **adversarially verified** (POCs run against this codebase);
> the feasibility caveats it surfaced are baked in rather than glossed.

## Problem

The system has **no injectable IO seam**:

- `backend/app/database.py:5-6` builds `AsyncIOMotorClient(settings.mongo_uri)` at **import time**.
- Every router handler calls the module-global `get_words_collection()` *inside* the handler
  (`words.py:45`, `etymology.py:22`/`:76`, `search.py:61`, `concept_map.py:27`/`:64`). A repo-wide grep
  for `Depends` in `backend/app` returns nothing — there is no override point.

Consequences:

1. The only way to exercise request → router → service → Mongo is a **full live stack**, so
   `tests/integration` (SPC-00013) **skips-as-pass** when the API is down, and `large-graph-perf.spec.js`
   `test.skip()`s on small data. **Green means "nothing ran," not "nothing broke."**
2. The most complex service, `TreeBuilder`, has its entire orchestration core **untested** — the three
   async tests in `test_tree_builder.py` pass *vacuously* (no assertions). `template_parser` has zero tests.
3. Two module-global caches (`lang_cache._code_to_name/_name_to_code`, `concept_resolver._concept_cache`)
   leak state across tests, making even a perfectly-seamed suite order-dependent.

## Goals

- One injectable seam at the Mongo boundary — constructor/`Depends` injection only; no global `db`, no
  import-time client.
- Four runnable tiers where the **lowest three run hermetically in CI with no live stack**.
- Error scenarios as first-class tests. Tests double as documentation.
- Build breaks on red, with an opt-in **discovery mode** so a failing spec can be written first.

## The tier model (this stack)

| Tier | Tests | Seam policy | Marker | Runs in CI? |
|------|-------|-------------|--------|-------------|
| **Tier 0** | Pure logic, no IO | no mocks | `tier0` | yes |
| **Tier 1** | The IO boundary itself | *is* the seam — **real ephemeral Mongo** | `tier1` + `requires_docker` | yes (skips loudly w/o Docker) |
| **Tier 2** | Orchestration | the **one** in-memory fake | `tier2` | yes |
| **Acceptance** | Full FastAPI app in-process | only the Mongo seam faked/seeded | `acceptance` | yes |

**Backend Tier 0** (pure, mostly already the proven model in `test_etymology_classifier.py` /
`test_phonetic_similarity.py`): `template_parser.normalize_word` (**untested today**, the core of the
SPC-00014 normalization class), `extract_ancestry`/`extract_cognates`/`node_id`, the classifier,
`phonetic_similarity.*`, `TreeBuilder.add_node/add_edge/result` **and the synchronous
`_build_ancestor_chain`** (Tier-0 with `col=None`, untested today), the pure `words.extract_*` and
`concept_map._extract_etymology_edges/_add_edge` helpers, `lang_cache.code_to_name/name_to_code`.

**Backend Tier 1** (small, **real Mongo only** — the fidelity-sensitive query contracts):
`suggest_concepts` collation range, `find_descendants` dotted-key `$elemMatch`, `_expand_polysemous`
nested `$arrayElemAt`, `_WORD_PROJECTION` `$slice`, `_augment_via_gloss` Unicode `$regex`, and the two
sibling-collection hops (`etymology_edges`, `languages`).

**Backend Tier 2** (the biggest current gap — against the single fake repo, no Mongo):
`TreeBuilder.expand_word` full control flow, `find_descendants` immediate-parent guard, `expand_cognates`
round-limiting + cycle termination, `_expand_compound_edges`; `concept_resolver.resolve_concept` strategy
selection; router handlers driven via `app.dependency_overrides` (type-filter branching, 404 + normalize
fallback, search dedupe/merge).

**Acceptance**: full app via `httpx.ASGITransport` (no live server). **Reuse the SPC-00013 fixtures**
(`tests/fixtures/wiktionary/*.json`, `query` + `system_output`) as expectations — seed the fake from the
input docs, assert the app returns `system_output`. This turns the live-only characterization suite into a
hermetic, CI-runnable mirror; keep the existing live path behind an opt-in `live` marker.

**Frontend**: there is **no frontend Tier 1/2** (the browser has no injectable IO seam of its own).
Tier 0 = pure JS via the existing jsdom/eval harness (`router.js` parse/build; `graph.js` pure helpers —
family classification, `linkifyEtymologyText`/escaping, `computeHopDistances` over a `{forEach}` fake, the
position/perf functions). Acceptance = Playwright E2E. **Recommendation:** extract
`similarity-worker.js`'s `levenshteinDistance`/`sharedPrefix` into a shared module so they become Tier-0
testable *and* can be cross-checked against the backend's `dolgopolsky_distance`; and replace
`large-graph-perf.spec.js`'s content-dependent `test.skip(nodeCount<=N)` (silent no-op on a small DB) with
a deterministic seeded corpus.

## The one seam

The Mongo IO boundary, expressed as a **repository port** injected through FastAPI `Depends`.

**Why a port, not the raw collection.** "The words collection" is *not actually one seam* here — code
reaches sideways through the Motor handle to sibling collections (`tree_builder.py:158`
`self.col.database["etymology_edges"]`; `lang_cache.py:18` `col.database.get_collection("languages")`). A
raw-collection fake must therefore emulate Motor's full cursor chain *and* `.database[...]`, and (verified
empirically) mongomock cannot faithfully emulate **collation** range matching. A small port collapses all
of that to a handful of `async def` methods returning plain Python lists — exactly the "pure-Python fake
above one seam" the philosophy prescribes.

```python
# backend/app/repository.py
class WordsRepository(Protocol):
    async def find_word(self, word, lang, etym=None, projection=None) -> dict | None
    async def find_descendants(self, lang_code, word, allowed_types, limit) -> list[dict]
    async def search_exact(self, q, limit) -> list[dict]
    async def search_prefix(self, q, limit) -> list[dict]
    async def etymology_groups(self, word, lang) -> list[dict]
    async def find_translation_hub(self, concept) -> dict | None
    async def find_by_pairs_with_ipa(self, pairs, pos) -> list[dict]
    async def find_by_gloss(self, concept, pos) -> list[dict]
    async def suggest_concepts(self, prefix, limit) -> list[dict]
    async def find_compound_edges(self, to_word, to_lang) -> list[dict]   # etymology_edges hop
    async def load_languages(self) -> list[dict]                          # languages hop
```

`MongoWordsRepository(WordsRepository)` holds the **real query strings** (this is what Tier 1
contract-tests against testcontainers). `FakeWordsRepository` is seeded from plain dict lists (Tier 2 /
Acceptance) and is **anchored to reality because the same assertions run against `MongoWordsRepository` at
Tier 1** — without that anchor a hand fake can return anything and hide a query bug.

## Refactor — staged, with honest reversibility

> **Honesty note (from adversarial review):** Steps 1-3 are genuinely minimal and reversible, but they
> only deliver the **Acceptance tier** + the import-loop fix. The **no-live-Mongo Tier-2** payoff requires
> **Step 4 (the port)**, which is a larger, *non-reversible* method-body refactor of the most complex
> untested service. Do **not** market Step 4's payoff under the "minimal/reversible" banner.

**Step 1 — move client creation out of import time.** Delete `database.py:5-6`; build the client in a
FastAPI `lifespan` in `main.py`, store `app.state.db`, `client.close()` on shutdown. This ties the client
to the app's running loop and removes the **pytest-asyncio loop-binding hazard** (Motor binds to the loop
captured at construction). *Blast radius: `main.py` +1, `database.py` −2 lines. Reversible.*

**Step 2 — add dependency providers** (`database.py`): `get_db(request) -> app.state.db`;
`get_words_collection(db=Depends(get_db)) -> db.words` (repurposes the existing name from a zero-arg getter
into a `Depends`-able provider).

**Step 3 — convert the 6 router call-sites** from `col = get_words_collection()` to
`col: AsyncIOMotorCollection = Depends(get_words_collection)`. **Services need zero changes** — `TreeBuilder`
already takes `col` via constructor; `concept_resolver.*`/`lang_cache.ensure_loaded` already take `col`.
*Blast radius of Steps 1-3: 4 files, ~12 net lines. The live HTTP path (SPC-00013, Playwright) is
unchanged.* This unblocks **Acceptance** via `dependency_overrides`.

**Step 4 (follow-up, larger, non-reversible) — introduce the port.** Extract the raw query bodies out of
`TreeBuilder`/`concept_resolver`/`lang_cache`/routers into `MongoWordsRepository`; `TreeBuilder.__init__`
takes `repo` instead of `col`. This collapses the seam to one and removes mongomock from the Tier-2 path.
**Smaller intermediate option** (reversible, compare on merits): keep raw-collection injection but provide
one hand-rolled `FakeCollection` implementing the exact small cursor surface used (incl. the `.database[...]`
hops) — unblocks Tier-2 without the full port.

**De-risking sequence (required).** Land the **hermetic Acceptance suite over Steps 1-3 first** (override
`get_words_collection` with a seeded fake/mongomock from the SPC-00013 fixture docs, assert `system_output`),
**then** do the Step-4 port surgery behind that net — the Acceptance snapshots become the regression net for
the `tree_builder` rewrite.

**Module-global caches.** `lang_cache` is read *synchronously inside pure functions*, so it cannot cleanly
move behind the async repo without threading a `LangResolver` through them. Decision: **keep it a module
global and add an autouse fixture** that resets `lang_cache._code_to_name/_name_to_code` and
`concept_resolver._concept_cache` before every test (the cheap, honest path). Threading a `LangResolver` is
a separately-costed item, not "fold it behind the repo."

## Tooling / runner wiring

- **Tier-1 engine = real ephemeral Mongo** (testcontainers-python / a throwaway `etymology_test` DB), **not
  mongomock**. Empirically, mongomock_motor 4.3.0 reproduces dotted `$elemMatch`, nested `$arrayElemAt`, and
  `$slice` faithfully but **silently ignores collation** — so `suggest_concepts` must be Tier-1-only with a
  **hard skip**, never discipline. mongomock is an *optional fast lane*, never the authority. Add a tiny CI
  **fidelity smoke** (the 4-operator probe) so a future mongomock upgrade that regresses an operator is caught.
- `pyproject.toml` `[tool.pytest.ini_options]`: register markers (`tier0 tier1 tier2 acceptance
  requires_docker discovery live`) so an unknown marker errors; keep `asyncio_mode=auto`,
  `asyncio_default_fixture_loop_scope=function`; widen `testpaths` to include an acceptance dir; a
  `pytest_collection_modifyitems` hook sorts by tier (lowest-first / fail-fast).
- `backend/requirements-dev.txt`: add **`httpx`** (ASGITransport — required regardless of Mongo strategy;
  currently **not installed**), `testcontainers[mongodb]`, optionally `mongomock-motor`. Gate the
  `acceptance` marker to **error loudly** if `httpx` is missing (mirror `requires_docker`).
- **Makefile**: `tier0/tier1/tier2/acceptance` (each `cd backend && pytest -m <tier>`, `FLAGS` pass-through);
  `test` chains them lowest-first; `discover` runs `pytest -m discovery --runxfail || true`; `test-all` gains
  the hermetic acceptance run; legacy `tests/integration` stays behind `make run` tagged `live`.

## First-class error scenarios (mapped to tiers)

Missing/unknown word → single orphan node, not 500 (Acceptance + Tier 2); normalization fallback fires only
when `normalized != raw` (Tier 0/2); malformed/named-arg/empty-string templates skipped not crashed (Tier 0);
affix-vs-component skip + ancestry dedupe in `extract_word_mentions` (Tier 0); **non-deterministic 50-cap** →
assert `count<=50` / membership, never identity (Tier 2; pinned exactly once the SPC-00014 deterministic-sort
lands); cognate cycle/round bound + ancestor/compound depth caps (Tier 2); concept hub→gloss fallback +
no-IPA exclusion + the empty-query `IndexError` at `concept_resolver.py:145` (Tier 1/2); `lang_cache`
unknown-code passthrough + cross-test contamination (Tier 0 + autouse reset); frontend `parseURL` typed
coercion + disconnected-graph + linkify escaping (Tier 0).

## Build-breaks-on-red + discovery mode

Default: red = nonzero exit = CI fails. Discovery mode: tests marked `@pytest.mark.discovery` are
`xfail(strict=False)` (or run via `make discover` with `|| true`) so a newly-written failing spec keeps the
build green until implemented; remove the marker when it goes green and it becomes build-breaking. This is
how SPC-00014's "sort-by-out-degree cap" assertion lives *before* its code exists (there is no port method to
compute out-degree yet — discovery-mark it, or add a `count_descendants` repo method).

## Verification

- `make tier0/tier1/tier2/acceptance` each green in isolation; `make test` runs all four lowest-first with
  **no live stack** (Tier 1 skips **loudly** without Docker; a CI gate fails if Tier 1 collected zero items
  in a Docker environment, so collation/`$elemMatch` coverage can't silently vanish).
- The SPC-00013 fixtures drive the hermetic acceptance suite to the same `system_output` the live suite
  asserts.
- `TreeBuilder.expand_word`/`find_descendants`/`expand_cognates` have **real assertions**; every
  `FakeWordsRepository` method has a **paired Tier-1 contract test** against testcontainers Mongo.
- No test monkeypatches a module global; an autouse fixture proves `lang_cache`/`_concept_cache` reset
  between cases.

## Out of scope

CI-provider configuration; the SPC-00014 behavioral changes themselves (native descendants, inflection
search) — this spec only provides the test architecture they plug into.
