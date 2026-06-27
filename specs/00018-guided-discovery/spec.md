# SPC-00018: Guided Discovery

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | — |
| **Modified-by** | — |
| **Depends on** | SPC-00015 (doublets power "did you know" cards) |

## Problem

The app opens on a single default word (*wine*) with no on-ramp for someone who doesn't already have
a word in mind. Hobbyists especially benefit from **discovery** — a reason to come back and a path
into the 10.4M-entry database that doesn't require knowing what to search. None of this exists today.

## Goals

- Give first-time and returning users compelling entry points that require no prior knowledge.
- Showcase the dataset's most interesting corners.
- Stay lightweight (no accounts, consistent with the app's local, no-tracking ethos).

## Proposed solution

### Entry points
- **Word of the day** — a deterministic daily pick (seeded by date) from a curated pool of
  etymologically rich words, shown on load as a dismissible suggestion.
- **Random / "Surprise me"** — a button that loads a random word with a good-sized, interesting tree
  (filter to entries with non-trivial ancestry so randoms aren't dead ends).
- **Curated tours** — themed, ordered word lists the user can step through:
  - *Wanderwörter* (sugar, tea, coffee, orange…) — words that traveled across many languages.
  - *Borrowed from Arabic* (alchemy, algebra, admiral, sofa…).
  - *False friends* and *surprising doublets* (salt/salary, shirt/skirt — via SPC-00015).
- **"Did you know" cards** — surprising shared-root facts surfaced from the doublets engine
  (SPC-00015) and borrowing data; one-tap to open the relevant graph.

### Backend support
- A small curated-content store (JSON or a `discovery` collection): tour definitions + the
  word-of-the-day pool.
- A `GET /api/discovery/random?min_tree=…` endpoint that samples a qualifying entry
  (e.g. `$sample` with an ancestry/descendant floor).
- `GET /api/discovery/tours` and `GET /api/discovery/word-of-the-day?date=…`.

## Out of scope
- Quiz/game mode (guess-the-ancestor, cognate match) — a follow-on hobbyist spec that can reuse the
  random + doublets endpoints here.

## Verification
- Loading the app offers a word of the day and a "Surprise me" that never lands on a bare,
  ancestry-less entry.
- Each tour steps through its words and renders each as a normal shareable graph URL.
- "Did you know" cards link to a graph that actually demonstrates the stated connection.
