# SPC-00014: Native Descendants & Inflection-Aware Search

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | SPC-00011 (changes descendant discovery + normalization), SPC-00012 (descendant edge sourcing) |
| **Modified-by** | SPC-00020 (test architecture: tiering, single Mongo seam, shared fixtures); SPC-00021 (pulls the R3 deterministic-cap slice forward as an interim alphabetical sort-before-limit; out-degree ranking remains here) |

## Problem

The descendant half of the etymology graph is reconstructed by an expensive reverse `$elemMatch`
lookup (`tree_builder.find_descendants`). Three defects follow from this (see
[AUDIT-2026-06 §A3](../../docs/AUDIT-2026-06.md#a3--correctness--test-gaps)):

1. **Non-deterministic truncation.** `find_descendants` (`tree_builder.py:215`) does `.limit(50)`
   with **no sort** — identical requests can return different descendants, which also destabilizes
   the SPC-00013 snapshot tests.
2. **Normalization mismatch.** Ancestor lookups fall back through `normalize_word`
   (`template_parser.py:11`), but the descendant match uses the **raw** `args.3`
   (`tree_builder.py:211`) — reconstructed/diacritic forms silently miss real links.
3. **Incompleteness.** The reverse lookup depends on every descendant storing its parent in exactly
   the matched string form, and is capped at 50. Kaikki already ships a curated **`descendants`**
   field that the app **ignores entirely**.

Separately, **search can't resolve inflected forms** (*ran*→*run*) because `forms`/`form_of`/`alt_of`
are unused, and search is case-sensitive — together a large class of "not found" misses
([§A4](../../docs/AUDIT-2026-06.md#a4--the-big-opportunity--unused-kaikki-data),
[§A5](../../docs/AUDIT-2026-06.md#a5--ux--accessibility--polish)). And the engine that does all of
this is **untested** (`test_tree_builder.py` stubs).

## Goals

- Use Kaikki's native `descendants` as the **primary** descendant source; keep reverse lookup as a
  **fallback** for entries lacking it.
- Make any remaining cap **deterministic and meaningful**.
- Resolve inflected/alternative search queries to their lemma.
- Establish real test coverage for `tree_builder` and the API endpoints.

## Proposed solution

### 1. Native descendants (primary) + reverse lookup (fallback)
- Parse the `descendants` field (nested `descendants[].descendants[]` tree, with `tags` like
  `borrowed`/`learned`) into `component`/`inh`/`bor` edges directly, no DB scan.
- Where `descendants` is absent or empty, fall back to the existing reverse `$elemMatch`.
- **Verify coverage first** (this is the gating unknown):
  `db.words.countDocuments({ descendants: { $exists: true, $ne: [] } })`.

### 2. Deterministic, significant cap
- When a cap still applies (native lists can be large), **sort before limiting** — e.g. by the
  descendant's own out-degree (most-connected first), then alphabetically — so the retained set is
  reproducible and the most important branches survive. Replaces the bare `.limit(50)`.

### 3. Consistent normalization
- Apply `normalize_word` on **both** sides of descendant matching (R4), matching the ancestor path.

### 4. Inflection-aware, case-insensitive search
- In `search.py` / `words.py`: when an exact/normalized lookup misses, consult `senses[].form_of`,
  `senses[].alt_of`, and `forms[]` to redirect to the lemma.
- Use the **already-built but unused** `word` text index for a case-insensitive path (R6); keep the
  case-sensitive prefix path for fast autocomplete.

### 5. Tests (R2)
The test **infrastructure** — the tier model, the single injectable `WordsRepository` seam, the shared
`FakeWordsRepository`, the conftest fixtures, and the runner/marker wiring — is defined by **SPC-00020
(Tiered Testing Architecture)**. SPC-00014 does not re-specify it; it adds these behavior-specific cases:

- **Tier 0:** `normalize_word` applied to **both** sides of descendant matching (R4) — pin the rule
  directly (`template_parser.py:11`); today only the SPC-00013 Q13 snapshot asserts the outcome.
- **Tier 2** (`find_descendants` over `FakeWordsRepository`): native `descendants`-field path is primary,
  reverse `$elemMatch` is fallback; the new deterministic cap (sort-by-out-degree-then-alphabetical)
  returns a **reproducible** set — assert stable membership across repeated runs (replacing the
  non-deterministic `.limit(50)`). *Until the sort code lands, mark this `@pytest.mark.discovery`* (there
  is no port method to compute out-degree yet — add a `count_descendants` repo method or discovery-gate it).
- **Tier 1** (real Mongo): the reverse-lookup `$elemMatch` and the native-`descendants` parse still match
  real Kaikki docs — seed one word with `descendants` populated and one without; also seed a descendant
  whose parent is stored in **raw** (diacritic/`*`) form vs. normalized form, asserting both are found
  (the only place R4's mismatch is catchable).
- **Tier 2 / Acceptance:** inflection-aware search resolves `forms`/`form_of`/`alt_of` to the lemma and the
  case-insensitive path returns results — driven through the same ASGITransport `app_client` SPC-00020
  provides. The SPC-00013 fixtures become Acceptance expectations; SPC-00014 adds *wine/window/bus* fixtures
  with `descendants` populated, plus a deliberately **cap-hitting** fixture (>50 real descendants).

### 6. Dead code (R7)
- Remove or clearly annotate `phonetic_similarity.build_similarity_edges` / `dolgopolsky_distance`
  as test-only (the API computes similarity in the Web Worker).

## Out of scope
- The word-families view (`derived`/`related`) — a separate future spec that reuses the `forms`
  plumbing introduced here.

## Verification
- `descendants`-sourced trees match or exceed reverse-lookup completeness on canonical words
  (*wine*, *window*, *bus*); SPC-00013 snapshots become stable across repeated runs.
- Searching an inflected form resolves to its lemma; case-insensitive queries return results.
- The SPC-00020 Tier-2 suite exercises `tree_builder` against the shared `FakeWordsRepository`; the
  deterministic cap makes the SPC-00013 Acceptance snapshots stable across repeated runs.
