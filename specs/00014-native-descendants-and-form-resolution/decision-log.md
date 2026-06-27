# Decision Log: SPC-00014 Native Descendants & Inflection-Aware Search

## Starting Question

The 2026-06 audit found that descendants are reconstructed via a capped (50), non-deterministic
(unsorted `.limit`), normalization-mismatched reverse `$elemMatch`, while Kaikki ships a curated
`descendants` field the app ignores. How should descendant discovery work — and can we fix the
correctness defects at the same time as unlocking inflection-aware search?

## Alternatives Considered

### Option A: Keep reverse lookup, just fix the defects
Add a sort + consistent normalization to the existing `find_descendants`.
- **Pros:** Smallest change; no new parsing.
- **Cons:** Still capped and still misses descendants that don't store the parent in the matched
  form. Leaves Kaikki's curated data on the floor. Doesn't address completeness.

### Option B: Replace reverse lookup with Kaikki's native `descendants` field
Parse `descendants` directly; drop the reverse scan.
- **Pros:** Curated, complete, no scan, no cap pressure, deterministic.
- **Cons:** Coverage is unknown until verified live; entries lacking the field would regress to no
  descendants. Risky as a hard cutover.

### Option C: Hybrid — native primary, reverse fallback (chosen)
Use `descendants` when present; fall back to the (now sorted + normalized) reverse lookup otherwise.
- **Pros:** Best completeness where data exists, no regression where it doesn't, fixes determinism
  and normalization regardless. Incremental and low-risk.
- **Cons:** Two code paths to maintain.

## Decision & Rationale

**Option C.** The hybrid captures the upside of curated data without betting the feature on unknown
coverage, and the determinism/normalization fixes apply to the fallback path too. Bundling the
inflection-aware search and the engine tests into the same spec is deliberate: all three problems
share the `tree_builder`/`template_parser`/search surface, and the new test fixture is needed to
land any of them safely.

### Sub-decision: cap strategy
Rather than removing the cap (some PIE roots have hundreds of descendants → graph explosion), keep a
cap but **sort by significance** (descendant out-degree, then alpha) so truncation is reproducible
and keeps the most informative branches. This directly resolves the audit's non-determinism finding.

### Sub-decision: verify coverage before cutover
The native-descendants path is gated on a live coverage check, since the audit's data figures are
code-derived (MongoDB was down). If coverage is low, the hybrid still ships value via the fixed
fallback.

## Participants

- **Human:** Requested the feature audit and approved a roadmap leading with the data foundation.
- **Claude (DA):** Audited the descendant logic, identified the unused `descendants`/`forms` fields,
  and proposed the hybrid + inflection-resolution + test plan.
