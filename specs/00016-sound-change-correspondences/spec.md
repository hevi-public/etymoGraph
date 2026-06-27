# SPC-00016: Sound-Change Correspondences

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | — |
| **Modified-by** | — |
| **Depends on** | SPC-00002 (phonetic precompute / Dolgopolsky tokens), SPC-00014 (reliable chains) |

## Problem

The detail panel shows a word's IPA in isolation, but the most illuminating phonetic story in
etymology is the **change between stages**: Latin *p* → Germanic *f* (Grimm's law), Latin *kt* →
Spanish *ch*, and so on. The app already has IPA (`sounds[].ipa`) and precomputed Dolgopolsky tokens
on most entries, but nothing aligns adjacent inheritance steps to show what changed. This is the
single feature that most raises the tool's credibility for linguists while staying genuinely
fascinating for hobbyists.

## Goals

- For an inheritance edge (ancestor → descendant), align their phonetic forms and **highlight the
  segments that changed**.
- Where possible, label the change with a recognizable correspondence (e.g. "p → f").
- Degrade gracefully when one side lacks IPA.

## Proposed solution

### Alignment
- Tokenize both endpoints' IPA into the existing phonetic tokens (`phonetic.tokens` /
  `dolgo_classes`).
- Align the two token sequences (Levenshtein/Needleman–Wunsch — the normalized Levenshtein distance
  already used for similarity gives the backbone) and classify each column as
  *kept / changed / inserted / lost*.

### Presentation
- A **"Sound change"** strip in the detail panel for the selected node, showing its form aligned
  against its immediate ancestor, with changed segments emphasized.
- Optional: surface a one-line summary on the inheritance **edge** ("p → f") when both endpoints
  have IPA and the change is a clean single-segment substitution.

### Correspondence labels (light touch)
- Start descriptive ("X → Y in this step"), not prescriptive. A small, well-known rule table
  (Grimm/Verner for Germanic) can annotate matching transitions, clearly marked as heuristic.

## Out of scope
- A full sound-law engine or reconstruction validator. This is a *visualization* of observed
  IPA differences, not a generative phonology.
- Regular-correspondence mining across the whole dataset (a research feature; future spec).

## Verification
- Latin *pēs/ped-* → English *foot* highlights the *p→f* / *d→t* correspondences.
- A step where one side lacks IPA shows the available form without a misleading alignment.
- Hobbyist read: the change is visible at a glance; linguist read: the alignment is segment-accurate.
