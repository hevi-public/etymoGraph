# SPC-00012: Precompute Compound/Affix Etymology Edges

| Field | Value |
|---|---|
| **Status** | implemented |
| **Created** | 2026-03-23 |
| **Modifies** | SPC-00011 (extends chain linking with compound decomposition) |
| **Modified-by** | — |

## Problem

When tracing etymology chains, words that are compounds (e.g., Old Norse "vindauga" = "vindr" + "auga") have their internal structure hidden. The tree builder only expanded compound/affix components for the **searched word** when it had no ancestry templates (`len(chain) == 1` gate in `tree_builder.py`). Ancestor nodes discovered during chain traversal never had their compound structure explored.

## Solution

### 1. ETL Precomputation (`backend/etl/precompute_edges.py`)

A standalone batch script (sync pymongo, following `precompute_phonetic.py` pattern) that:

- Scans all documents with compound/affix templates (`af`, `affix`, `suffix`, `prefix`, `compound`, `blend`)
- Extracts component words from template args (positions 2-5, skipping hyphenated affixes)
- Validates each component's existence in the `words` collection (with LRU cache)
- Stores edges in a dedicated `etymology_edges` collection

**Edge schema:**
```json
{
  "from_word": "vindr",
  "from_lang": "Old Norse",
  "from_lang_code": "non",
  "to_word": "vindauga",
  "to_lang": "Old Norse",
  "to_lang_code": "non",
  "edge_type": "component",
  "source_template": "compound",
  "from_exists": true
}
```

**Indexes:** `(to_word, to_lang)` and `(from_word, from_lang)` for bidirectional lookup.

### 2. Tree Builder Integration (`tree_builder.py`)

New `_expand_compound_edges(chain)` method:

- Queries `etymology_edges` for **every** node in the ancestor chain (not just the searched word)
- Adds component nodes and edges to the graph
- Traces each component's own ancestry chain upward (e.g., "vindr" → Proto-Germanic *windaz → PIE)
- Recurses up to 2 levels deep for compounds-of-compounds

Called from `expand_word()` after building the ancestor chain, independent of the existing `_add_mention_edges` fallback.

## Result

Searching "window" now produces a branching graph:

```
PIE *h₂wéh₁n̥ts → *windaz → vindr ↘
                                     vindauga → wyndowe → window
   PIE *h₃ekʷ- → *augô → *ᚨᚢᚷᛟ → auga ↗
```

## Stats

- 1,173,044 documents processed (10.4M total, ~11% have compound/affix templates)
- 1,825,481 edges created
- 86.6% component match rate (components found in DB)
- Processing time: ~180s
