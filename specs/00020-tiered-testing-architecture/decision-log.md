# Decision Log: SPC-00020 Tiered Testing Architecture

## Starting Question

The 2026-06 audit named untested core logic as the top correctness risk (R2): `tree_builder.py`'s
orchestration is covered only by vacuous stubs, the API has no test that runs without a live stack, and the
SPC-00013 integration suite skips-as-pass when the API is down. Shortly after, the `bdd-tiered-testing`
skill (from a Kotlin/Spring project) was added. **How should that skill's philosophy — "mock at exactly one
seam" + a tiered architecture — be adapted to this Python/FastAPI/Motor/JS stack, and is it even feasible
given the import-time global Mongo client?**

## Alternatives Considered

### Tier-1 IO engine: mongomock vs. real ephemeral Mongo vs. a port fake
- **mongomock everywhere** — fast, no Docker. *But* empirically (mongomock_motor 4.3.0, run against this
  code's actual queries) it **silently ignores collation**, so `suggest_concepts` would get a false green.
  It reproduces dotted `$elemMatch`, nested `$arrayElemAt`, and `$slice` faithfully — better than the audit
  feared — but cannot be the authority for the fidelity-sensitive set.
- **Real ephemeral Mongo (testcontainers)** — authoritative for every operator by definition; needs Docker,
  so must skip cleanly. Chosen as the **Tier-1 authority**, kept small (only the query contracts).
- **Hand fake of a repository port** — pure-Python, no Mongo, deterministic; can lie if unanchored. Chosen
  as the **Tier-2 seam**, anchored by running the *same assertions* against the real repo at Tier-1.

### Seam shape: raw Motor collection vs. a repository port
- **Raw collection** injected via `Depends` — minimal diff, but "the collection" isn't one seam: code reaches
  `self.col.database["etymology_edges"]` and `...get_collection("languages")`, so a fake must emulate Motor's
  full cursor chain *and* collation. Brittle — the very thing the philosophy forbids.
- **Repository port** — collapses the seam to a handful of `async def` methods returning plain lists. Chosen
  as the target, but explicitly staged (see below) because it is the larger, non-reversible part.

### Framing of the refactor — the adversarial correction
The initial synthesis presented the whole refactor as "minimal and reversible." An adversarial skeptic
**refuted** that framing (high confidence): Steps 1-3 (inject the seam) *are* minimal/reversible, but they
inject a raw collection and therefore deliver only the Acceptance tier + the import-loop fix. The headline
benefit — **no-live-Mongo Tier-2 tests of `tree_builder`** — requires Step 4 (the port), a non-reversible
method-body rewrite of the most complex untested service. Two other skeptics confirmed the seam mechanics by
running POCs on this codebase (a hand fake drove `expand_word` end-to-end with no Mongo; `dependency_overrides`
drove the ASGI app to 200/404 with the real client never constructed).

## Decision & Rationale

Adopt the four-tier model with the **MongoDB boundary as a single injectable repository port**, but **stage
it honestly** and **sequence it to de-risk**:

1. **Steps 1-3 (reversible):** kill the import-time client (lifespan + `app.state.db` — also fixes the
   pytest-asyncio loop-binding hazard), add `Depends` providers, convert the 6 router call-sites. Unblocks the
   **hermetic Acceptance tier**.
2. **Land the Acceptance net first:** reuse the SPC-00013 fixtures as hermetic expectations over Steps 1-3.
3. **Step 4 (larger, non-reversible) behind that net:** extract the `WordsRepository` port so Tier-2 runs
   against a pure-Python fake with no Mongo — the Acceptance snapshots are the regression net for the surgery.

Rationale: this gives the philosophy's "one seam, real code above it" guarantee while being truthful about
cost and risk. The adversarial pass converted three latent traps into explicit requirements: **collation is
Tier-1-only with a hard skip**; **SPC-00014's two flagship bugs (unsorted cap, raw-vs-normalized) live inside
the port method and are catchable only at Tier-0/Tier-1, never behind the fake**; and the **module-global
caches need a mandatory autouse reset** (with `lang_cache` staying global because it is read synchronously
inside pure functions). The deterministic-cap assertion that has no code yet is handled by **discovery mode**.

### Sub-decision: SPC-00020 owns the test architecture; SPC-00014 consumes it
SPC-00014's ad-hoc §5 ("add a fixture, fill the stubs") is superseded by reference: SPC-00014 keeps only its
*own* behavior-specific cases and points at SPC-00020 for the tier model, the seam, and the runner — giving
the bidirectional `Modifies`/`Modified-by` traceability CLAUDE.md requires.

## Participants

- **Human:** Added the `bdd-tiered-testing` skill and nudged toward applying it to the testing gap.
- **Claude (DA):** Ran a verification workflow — four parallel analyses (seams, test inventory, Tier-0
  catalogue, tooling feasibility) → synthesis → three adversarial skeptics (async/Motor, query-fidelity,
  refactor-blast-radius). The refutation reshaped the spec from an oversold "minimal refactor" into the staged,
  acceptance-net-first plan recorded here.
