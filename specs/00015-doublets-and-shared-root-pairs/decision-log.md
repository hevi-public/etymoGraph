# Decision Log: SPC-00015 Doublets & Shared-Root Pairs

## Starting Question

The audit's roadmap calls for a "flagship" etymology feature that serves both hobbyists (delight)
and linguists (rigor). Doublets — same-language words from a shared ancestor via different routes —
are a strong candidate because the data already encodes them. How should they be detected and shown?

## Alternatives Considered

### Option A: Phonetic-similarity grouping within a language
Reuse the Dolgopolsky machinery to cluster similar-sounding same-language words.
- **Pros:** Reuses existing concept-map code.
- **Cons:** Phonetic similarity is **not** doublethood — *shirt/skirt* are doublets but many
  similar-sounding words are unrelated, and some doublets (*frail/fragile*) aren't that close
  phonetically. Wrong signal.

### Option B: Shared-ancestor detection from etymology chains (chosen)
Two same-language words are doublets iff their ancestry chains share a node reached by different
immediate parents.
- **Pros:** Provenance-correct (this is what "doublet" actually means); reuses ancestor/descendant
  machinery from SPC-00014; precise.
- **Cons:** Needs reliable descendant data — hence the dependency on SPC-00014.

### Option C: Curated doublet list
Ship a hand-curated list of famous doublets.
- **Pros:** Zero false positives; great for "did you know" cards (SPC-00018).
- **Cons:** Tiny coverage; not a general feature. Better as a *complement* (a tour) than the
  mechanism.

## Decision & Rationale

**Option B**, with Option C's curated list deferred to SPC-00018 as a discovery tour. Detecting
doublets from shared ancestry is the only approach that is both general and correct. A precomputed
collection mirrors the SPC-00012 precedent if query-time cost proves high; the spec leaves that as
an implementation switch pending measurement.

### Sub-decision: doublets vs. cognates
Doublets are intra-language; cross-language relatives remain the existing `cog` feature. Keeping the
concepts distinct avoids confusing users and keeps each feature's semantics clean.

## Participants

- **Human:** Approved a balanced roadmap with a flagship feature.
- **Claude (DA):** Proposed doublets as the flagship, grounded the detection in existing
  ancestor/descendant machinery, and separated it from phonetic similarity and cognates.
