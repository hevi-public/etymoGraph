---
name: mongodb-motor-data
description: MongoDB persistence for the Etymology Explorer FastAPI backend using Motor (async) — deliberately schemaless over the Kaikki dump, no ORM/ODM. Use this whenever working with the database layer — the single collection seam and DI providers, query patterns over etymology_templates ($elemMatch with dotted args, sort-before-limit determinism, collation, projections for 100KB docs), index discipline, bounded recursion caps in tree building, the precompute-to-collection ETL pattern (etymology_edges, layouts cache), the real-test-Mongo strategy and mongomock fidelity limits, or profile/env isolation so tests never touch the 10.4M-doc production DB.
---

# MongoDB + Motor for Etymology Explorer

Adapted from the HAIP project's `sqlite-spring-jdbc` skill (hevi-public/haip). HAIP's persistence
is SQLite + JdbcTemplate + Flyway; none of that tech transfers, but its durable rules do — one
injectable seam, real-DB tests for the queries themselves, termination guards on recursive walks,
deliberate index/migration discipline, and rail-tested config isolation. Storage here is
**MongoDB 7 via Motor** (async), schema-free over the Kaikki JSONL dump (10.4M docs in `words`),
queried with hand-written filters — an ODM buys nothing on a read-mostly corpus whose shape is
dictated upstream. This is the persistence seam of [[bdd-tiered-testing]].

## The seam

- `backend/app/config.py`: one setting, `mongo_uri` (env `MONGO_URI`, default
  `mongodb://mongodb:27017/etymology` — the compose service name).
- `backend/app/database.py`: historically built `AsyncIOMotorClient` at **import time** with
  module-global `db` — the reason nothing below the routers was hermetically testable, and a
  pytest-asyncio hazard (**Motor binds to the event loop captured at construction**; an
  import-time client binds the wrong loop under test). SPC-00020 Steps 1–3 (landing with
  SPC-00021 Phase 0) move creation into a FastAPI `lifespan`, store the client on `app.state`,
  and expose `Depends`-able providers; routers take the collection via `Depends`, services take
  it via constructor (as `TreeBuilder` already does).
- Sideways hops exist and are part of the seam's surface: `tree_builder.py` reaches
  `col.database["etymology_edges"]`, `lang_cache` reaches `col.database.get_collection("languages")`.
  Any fake must implement the `.database[...]` hop; the eventual SPC-00020 Step-4 repository port
  collapses these into explicit methods.
- ETL scripts (`backend/etl/*.py`) use **sync pymongo** deliberately — they are standalone batch
  jobs, never imported by the request path. Keep that separation.

## Collections

| Collection | Written by | Read by | Notes |
|---|---|---|---|
| `words` | `etl/load.py` (`make load`) | everything | 10.4M Kaikki docs; entries can exceed 100KB — always project |
| `etymology_edges` | `etl/precompute_edges.py` (`make precompute-edges`) | `tree_builder._expand_compound_edges` | precomputed compound/affix edges (SPC-00012) |
| `languages` | ETL | `lang_cache` | code↔name mapping |
| `layouts` (SPC-00021) | layout endpoints, write-through | layout endpoints | cache; `_id` = sha256 of canonical request key incl. `algo_version` |

## Query gotchas (each one is a Tier-1 test target)

- **Dotted positional args in `$elemMatch`.** Descendant lookup matches template arguments by
  position: `{"etymology_templates": {"$elemMatch": {"name": {"$in": [...]}, "args.2": lc,
  "args.3": word}}}`. Fakes must reproduce this exactly; real-Mongo contract tests keep them honest.
- **Sort before limit, always, when a cap exists.** The historical bug: `find_descendants` did
  `.limit(50)` with **no sort** — Mongo returns *some* 50 matches in unspecified order, so
  identical requests returned different graphs and destabilized the SPC-00013 snapshots (audit
  R3). The fix (SPC-00021 Phase 0) sorts `[("word",1),("lang",1),("pos",1),("etymology_number",1)]`
  before the limit — a bounded top-k, deterministic, content-based (never sort on `_id`: it
  changes across reloads). **Rule: any `.limit(n)` on a multi-match query carries an explicit
  deterministic sort**, and its test asserts stable membership across repeated runs.
- **Index-shaped predicates.** Search uses exact match then case-sensitive prefix regex `^q`
  (anchored regexes can use the index; case-insensitive ones cannot — that trade-off is why
  inflection/case handling is SPC-00014's job, not a quick `$options: "i"`).
- **Collation is real-Mongo-only.** `suggest_concepts` uses collation range matching, which
  mongomock **silently ignores** (verified in SPC-00020's adversarial review) — such tests are
  Tier-1 with a hard skip outside Docker, never faked.
- **Project or drown.** Entries with `sounds`/`senses` can exceed 100KB. Request-path reads use
  explicit projections (`{"_id": 0, "word": 1, ...}`); analysis via the MongoDB MCP uses
  `aggregate` + `$project` and `responseBytesLimit` (see CLAUDE.md's MCP best practices).

## Index discipline

`etl/load.py` creates indexes with `IndexModel`s right after loading — that is the single home for
`words` indexes; precompute scripts create their own collection's indexes at the end of their run.
Rules carried over from HAIP's index migrations:

- **Match the index to the read**: equality columns first, then the sort columns (the
  `etymology_templates.name/args.2/args.3` index serves the `$elemMatch`; if the new
  sort-before-limit shows a sort stage in `explain()`, extend the index rather than eating a
  per-request in-memory sort of high-fanout matches).
- **A unique index over populated data needs a dedupe shipped with it**, plus a collision-free
  insert path for future writes (the `layouts` cache sidesteps this by making the canonical
  request hash the `_id`).
- Check plans with `explain("executionStats")` when touching a hot query; "it returned the right
  rows" says nothing about how.

## Bounded recursion: termination is a property, and it's tested

HAIP bounds its recursive CTEs with a `lvl < 10000` guard; here the tree walk is **application-level
recursion** in `tree_builder.py`, and every walk carries an explicit bound:

- `max_descendant_depth` (1–5, default 3) caps `find_descendants` recursion; `max_ancestor_depth`
  (default 10) caps the chain walk; `MAX_DESCENDANTS_PER_NODE = 50` caps fanout;
  `DEFAULT_MAX_COGNATE_ROUNDS = 2` caps `expand_cognates`; `skip_descendant_ids` and edge/node
  dedup (`add_edge` returning False) break cycles.
- These are termination guarantees against cyclic/corrupt etymology data, not correctness tuning —
  a healthy graph never approaches them. **Test them as termination properties** (Tier 2 over the
  fake: a forged cognate cycle terminates within the round cap; depth caps hold) — SPC-00021
  Phase 0 fills exactly these previously-vacuous tests.

## The precompute-to-collection pattern (copy `precompute_edges.py`)

Any expensive derivation that is stable per data-load goes through the same shape:

1. Standalone sync script under `backend/etl/`, run as `python -m etl.<name>` via a Make target
   with `FLAGS` pass-through.
2. **Idempotent by default**: skip if the target collection is already populated; `--reprocess`
   drops and rebuilds.
3. Batch writes (`insert_many`, 5000/batch) with progress + rate logging; `lru_cache` for hot
   existence checks.
4. **Create the collection's indexes at the end of the run.**
5. The request path only *reads* the collection.

`etl/precompute_phonetic.py` is the second instance (bulk `UpdateOne` back onto `words`; note its
`lingpy` dependency is **not** in requirements — the Makefile documents the manual install). The
SPC-00021 `layouts` cache is the third, with two twists: written through from the request path
(fire-and-forget), and invalidated by `algo_version` bump + a `node_ids_hash` check against the
freshly built graph (a stale cache after a data reload self-invalidates).

## Test-DB strategy (per tier)

- **Tier 1 = real ephemeral Mongo**: testcontainers-python or a throwaway `etymology_test` DB.
  This is the authority for query semantics ($elemMatch, sort, collation, `$slice`, Unicode regex).
  Skips **loudly** without Docker; CI fails if Tier 1 collects zero tests in a Docker-capable
  environment.
- **Tier 2/Acceptance = the one fake** (`backend/tests/fakes.py::FakeWordsCollection`), seeded
  from plain dicts / SPC-00013 fixture docs, implementing only the surface actually used —
  including `.sort()` (so determinism is assertable) and the `.database[...]` hop. mongomock is at
  most an optional fast lane, never the authority (collation gap above); if used, keep a fidelity
  smoke test probing the four risky operators so a regression in a future version is caught.
- **Rail test**: under any test profile the resolved Mongo target must be a test database — assert
  it, don't assume it. A test run pointed at the real `etymology` DB can (at best) hammer 10.4M
  docs and (at worst) mutate `layouts`/precompute collections.
- Per-test reset: fresh fake per test (see [[fastapi-acceptance-bdd]]); for Tier-1, drop the
  ephemeral DB's collections between tests — plus the autouse reset of the `lang_cache`/
  `concept_resolver` module-global caches, which outlive any DB reset.

## Data-shape notes

The Kaikki field reference (etymology_templates types `inh/bor/der/cog`, mention templates,
`sounds[]` structure, full-chain-ancestry semantics) lives in CLAUDE.md § "Kaikki Data Notes" —
that section is the source of truth for what documents look like; keep new query code consistent
with it rather than re-deriving shapes from samples.

## Verify

- `make test` (tiers 0–2 + acceptance) green with no stack; Tier 1 green inside Docker.
- `make run && make test-integration` green over the live stack (opt-in `live` tier).
- After ETL changes: `make load`/`make precompute-edges` idempotency — second run skips; 
  `--reprocess` rebuilds; indexes exist (`db.collection.getIndexes()` via the MongoDB MCP).
- After query changes: `explain()` shows the intended index; determinism tests still pass twice in
  a row with identical output.
