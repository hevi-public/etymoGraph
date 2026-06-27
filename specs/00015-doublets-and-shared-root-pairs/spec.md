# SPC-00015: Doublets & Shared-Root Pairs

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | — |
| **Modified-by** | — |
| **Depends on** | SPC-00014 (reliable descendant/ancestor data) |

## Problem

The graph traces one word's lineage, but it never surfaces one of etymology's most delightful and
instructive patterns: **doublets** — two (or more) words in the *same* language that descend from
the *same* ancestor by *different* routes. Classic examples:

- *shirt* (inherited, Old English) and *skirt* (borrowed from Old Norse) ← Proto-Germanic
  *\*skurtijǭ*
- *guard* / *ward*, *cattle* / *chattel*, *frail* / *fragile*, *salt* and *salary* (both ← Latin
  *sāl*)

These shared-root pairs are a flagship "wow" feature for hobbyists and a genuine comparative-method
artifact for linguists. The data already supports finding them — they are exactly the words that
share a common ancestor node.

## Goals

- Detect, for a given word, its doublets (same language, shared ancestor, distinct paths).
- Present them prominently in the detail panel and optionally highlight the pair in the graph.
- Be reasonably precise (a true doublet shares an ancestor; mere cognates in *other* languages are
  the existing cognate feature, not doublets).

## Proposed solution

### Detection
- A doublet of word *W* (lang *L*) is another word *W′* in *L* whose ancestor chain shares a node
  with *W*'s chain, where the two reach that shared ancestor by **different immediate parents** (one
  typically `inh`, the other `bor`/`der`).
- Compute via the ancestor chains already built by `tree_builder`: for each ancestor node, gather
  other words in *L* that descend from it (reusing the descendant machinery from SPC-00014), then
  filter to those whose path diverges from *W*'s.
- Consider **precomputing** a `doublets` collection (keyed by `(word, lang)`) the way SPC-00012
  precomputes compound edges, if query-time cost is high.

### Presentation
- A **"Doublets"** section in the detail panel: each doublet links to its own graph, annotated with
  the shared ancestor and the two routes (e.g. "*skirt* — via Old Norse; shares *\*skurtijǭ*").
- Optional graph affordance: a badge on words that have doublets; clicking highlights the pair and
  the shared-ancestor path.

## Out of scope
- Cross-language cognate pairs (already covered by the `cog` filter).
- Semantic judgement of whether a pair is a "true" doublet vs. a chance resemblance — we rely on
  shared-ancestor provenance, not phonetics.

## Verification
- *shirt* surfaces *skirt* (and vice versa) with shared ancestor Proto-Germanic *\*skurtijǭ*.
- *salary* surfaces *salt*/*sal-*; *guard* surfaces *ward*.
- A word with no shared-root sibling shows no Doublets section (no false positives from ordinary
  cognates).
