# Decision Log: SPC-00016 Sound-Change Correspondences

## Starting Question

The app has IPA and precomputed phonetic tokens but never shows the *change* between etymological
stages — which is where the linguistic insight lives. How can we surface regular sound changes
without building a full historical-phonology engine?

## Alternatives Considered

### Option A: Hardcode famous sound laws (Grimm, Verner, …) and tag matching edges
- **Pros:** Recognizable, impressive labels.
- **Cons:** Brittle and Indo-European/Germanic-biased; says nothing for the thousands of other
  transitions; high effort to encode rules correctly.

### Option B: Align IPA per inheritance step and show the diff (chosen)
Compute a segment alignment between adjacent forms and highlight what changed; add rule labels only
as a light, clearly-heuristic garnish.
- **Pros:** Works for *any* pair with IPA, in any language family; reuses the existing tokenizer and
  distance metric; honest (shows observed differences, claims no theory).
- **Cons:** Alignment can be imperfect for big phonological jumps or sparse IPA.

### Option C: Mine regular correspondences statistically across the corpus
- **Pros:** The "real" comparative-method output.
- **Cons:** A research project in itself; far beyond this spec. Deferred.

## Decision & Rationale

**Option B.** Visualizing observed per-step IPA differences is the highest insight-per-effort move
and degrades gracefully. It builds directly on SPC-00002's phonetic tokens and the normalized
Levenshtein metric already in the codebase. Rule labels are kept optional and explicitly heuristic so
the feature stays trustworthy. Statistical correspondence mining (Option C) is noted as a future
research spec.

### Sub-decision: panel strip vs. edge label
Both — a detailed aligned strip in the detail panel (rich) plus an optional terse edge summary
(glanceable). The edge label only appears for clean single-segment substitutions to avoid clutter.

## Participants

- **Human:** Approved a roadmap balancing linguist rigor and hobbyist delight.
- **Claude (DA):** Proposed alignment-based visualization over a hardcoded rule engine; scoped out
  full sound-law modeling and corpus-wide correspondence mining.
