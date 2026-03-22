# SPC-00011: Etymology Chain Linking Audit & Fix

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-03-22 |
| **Modifies** | SPC-00001 (edge resolution from templates) |
| **Modified-by** | — |

## Problem Statement

The etymology graph builds chains by reading `etymology_templates` from Kaikki/Wiktionary data. Three systemic issues prevent proper chain linking, causing broken navigation, incomplete trees, and phantom nodes.

## Findings

### 1. Template word != DB headword (spelling mismatch)

Templates reference ancestors using Wiktionary's **display spelling** (diacritics, asterisks for reconstructed forms), but the DB stores **headwords** stripped of these:

| Template `args.3` | DB `word` field | Language | Mismatch type |
|---|---|---|---|
| `wīn` | `win` | Old English | macron stripped |
| `vīnum` | `vinum` | Latin | macron stripped |
| `*wīn` | `wīn` | Proto-West Germanic | asterisk prefix |
| `*wīną` | `wīną` | Proto-Germanic | asterisk prefix |
| `*wóyh₁nom` | `wéyh₁ō` | Proto-Indo-European | different ablaut grade |

**What works**: `find_descendants()` queries `args.3` template-to-template — no document lookup needed, so descendant expansion is unaffected.

**What breaks**:
- Cognate expansion (`tree_builder.py:189`) — `find_one({word: node["label"]})` uses template-derived label
- Mention edges (`tree_builder.py:109`) — same pattern
- Frontend node click → word navigation → API lookup fails
- Any code path: template data → node label → document lookup

### 2. Multiple entries per word+lang (polysemy / POS)

- 47,703 docs with null word/lang
- Extreme duplicates: Japanese "上下" (23 entries), English "a" (19 entries)
- `find_one` picks arbitrarily — may return wrong etymology for a polysemous word
- No mechanism to distinguish "bank" (river) from "bank" (financial)

### 3. Conflicting ancestry across documents

Different words claim different ancestries for shared intermediaries:
- English "wine" traces to PIE `*wóyh₁nom`
- Latin "vinum" traces to PIE `*wéyh₁ō`

These are different ablaut grades of the same PIE root `*weyh₁-` — linguistically correct, but creates graph fragmentation (two PIE nodes that should be connected).

### DB Population Reference

| Language | Code | Doc count | Notes |
|---|---|---|---|
| Old English | ang | 62,812 | headwords lack macrons |
| Proto-West Germanic | gmw-pro | 5,377 | headwords lack `*` prefix |
| Proto-Germanic | gem-pro | 5,689 | headwords lack `*` prefix |
| Proto-Indo-European | ine-pro | 1,808 | headwords lack `*` prefix |
| Latin | la | 883,915 | headwords lack macrons |
| Middle English | enm | exists | `wyn` found, links work |
| **Total** | | **10.4M** | |

## Approach: Iterative Sprints

Each sprint is independently valuable. Findings from each sprint inform the next.

---

### Sprint 1: Quantify the Problem

**Goal**: Measure chain breakage rates and categorize mismatch types.

**Tasks**:
1. Sample 50 common English words, trace their full ancestry chains
2. For each ancestor node, check if a matching document exists in the DB
3. Categorize mismatches:
   - Macron stripping (ī→i, ā→a, ū→u, ē→e, ō→o)
   - Asterisk prefix (`*word` in template, `word` in DB)
   - Different word form (ablaut, alternate spelling)
   - Document missing entirely (no entry under any spelling)
4. Check raw Kaikki JSONL for unused fields: `forms`, `redirects`, `etymology_number`, `etymology_id`
5. Cross-reference with Wiktionary API: `https://en.wiktionary.org/w/api.php?action=parse&page={word}&prop=wikitext&format=json`

**Output**: Breakage rate statistics, mismatch category distribution, list of potentially useful Kaikki fields.

---

### Sprint 2: Design Resolution Strategy

**Goal**: Choose and design the linking fix based on Sprint 1 data.

**Candidate approaches** (evaluate based on Sprint 1 findings):

**Option A — Query-time normalization**:
- On document lookup failure, retry with normalized form (strip macrons, strip `*`)
- Add normalization function to `template_parser.py`
- Pros: No ETL changes, immediate fix
- Cons: Runtime cost per lookup, potential false positives

**Option B — ETL-time edge collection**:
- During `load.py`, extract all template references into an `edges` collection:
  ```
  {from_word, from_lang_code, to_word, to_lang_code, type, template_word}
  ```
- Separate graph structure from word documents
- Pros: Clean, pre-computed, no spelling issues
- Cons: Requires ETL re-run, estimated ~50M+ edge docs

**Option C — Alias/mapping table**:
- Build `word_aliases` collection at ETL time: `{template_form, headword_form, lang_code}`
- Query alias table when exact match fails
- Pros: Small collection, fast lookups
- Cons: Still requires ETL change

**Output**: Chosen approach with implementation design.

---

### Sprint 3: Handle Polysemy

**Goal**: Disambiguate multiple etymologies for the same word+lang.

**Investigation**:
- Does Kaikki include `etymology_number` or `etymology_id` fields?
- Can we use POS + first gloss as disambiguator?
- UI: should users pick which meaning, or show all etymologies merged?

**Output**: Disambiguation strategy for the chosen Sprint 2 approach.

---

### Sprint 4: Implementation

Implement the chosen strategy from Sprints 2-3.

---

## Verification

After each sprint, test with these words and verify chain completeness:
- `wine` (English) — known: OE "wīn" → DB "win" mismatch
- `cheese` (English) — has `etymon` template + cognates
- `water` (English) — deep PIE chain, broad descendant tree
- `mother` (English) — universal cognate network
- `fire` (English) — contested etymology

Cross-check against Wiktionary API for expected chain depth.

## Critical Files

| File | Relevance |
|---|---|
| `backend/etl/load.py` | Data loading, index creation |
| `backend/app/services/tree_builder.py` | Core chain building (lines 54, 109, 134, 189) |
| `backend/app/services/template_parser.py` | Template extraction, node_id generation |
| `backend/app/routers/etymology.py` | API endpoints for chain/tree |
| `frontend/public/js/graph.js` | Node click → word navigation |
