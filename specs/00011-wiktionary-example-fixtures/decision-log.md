# Decision Log — SPC-00011: Wiktionary Example Fixtures

## Starting Question

We want integration tests that protect the etymology API surface against regressions. Wiktionary has well-known quirks — disjunctive origins, compounds that redirect to base words, reconstructed forms with no main-namespace page — that our Kaikki-derived pipeline may flatten or drop. Before writing test assertions, we need a set of example words with known-correct expected output. **How should the fixture data be sourced and structured?**

## Alternatives Considered

### Option A: Hand-encode expected output from Wiktionary pages

- Pro: True independent ground truth; tests would catch any system divergence from Wiktionary.
- Con: Encoding the tree for `alchemy` (Arabic→Greek with cognates) by hand is tedious and error-prone — humans get edge directions, `level` numbers, and language-name spellings wrong. Doesn't scale beyond a handful of words.
- Con: Doesn't surface the *structural* gaps (e.g., compounds dropped, calques dropped) — those need a comparison artifact.

### Option B: Capture live API output as the fixture

- Pro: Trivially reproducible by the collector script; correct by construction for any word the system already handles.
- Con: It's a regression baseline, not ground truth. If the system has a bug today, the fixture freezes that bug into the test.
- Con: Doesn't capture what Wiktionary *actually* says, so quirks the system silently drops never appear in the fixture.

### Option C: Three-layer schema — `wiktionary_reference` (hand-encoded) + `system_output` (live capture) + `known_gaps` (explicit deltas)

- Pro: Combines both signals. Regression tests assert `system_output` is stable; correctness tests assert `system_output ⊇ wiktionary_reference` for non-gapped items.
- Pro: `known_gaps` makes the gap between Wiktionary truth and system behavior an explicit, reviewable artifact. When we later improve compound handling, a flag flips and a previously-tolerated assertion starts holding — the test guides the work.
- Pro: The hand-encoded layer can be sparse (just the primary chain + alternative theories), keeping the human effort to ~5 minutes per word.
- Con: Schema is heavier; collector can only auto-fill `system_output` + heuristic `known_gaps` guesses, so a human cross-check pass is required before commit.

### Option D: Capture-only with separate gap docs

- Pro: Simplest schema.
- Con: Splits related information across two artifacts; gap docs rot easily.

## Decision & Rationale

**Option C.** The user's stated goal is "ensure that we are consistent with Wiktionary" — that explicitly requires both the system output and what Wiktionary actually shows. Option B alone is insufficient (it can't detect what the system silently drops). Option A alone is impractical (manual encoding doesn't scale).

The `known_gaps` layer is the key innovation: it converts "the test fails because the system is incomplete" into "this gap is acknowledged; the day it's fixed, flip the flag and the test starts asserting the new behavior." This keeps the test suite honest without becoming a perpetual TODO list.

Word set: expanded from the initial six canonical examples to eleven, each chosen to exercise a specific quirk class (Q1–Q12 in `spec.md`). Twelve quirks were identified during Wiktionary research — each word covers one or more.

Script transport: HTTP to live `make run` services (via `pymongo` + stdlib `urllib`) rather than in-process FastAPI with `httpx`. Reason: the user must have `make run` going to populate Mongo anyway; reusing the live API matches how the rest of the system is tested and avoids adding `httpx` to runtime deps.

Integration tests themselves are out of scope for this PR. Scoping the collection separately keeps review tractable; the follow-up PR can then focus purely on test wiring (test-DB strategy, conftest fixture loader, `make test-integration`).

## Participants

- **Human** — initially proposed collecting Wiktionary examples; rejected the first plan draft to insist on real research into Wiktionary quirks; named the three primary issue classes (dead links, conditional origins, compound back-references).
- **Claude (Development Agent)** — researched Wiktionary via WebSearch (direct fetch blocked by sandbox `host_not_allowed`), identified 9 additional quirks (Q4–Q12) beyond the three named, designed the three-layer schema and collector script.
