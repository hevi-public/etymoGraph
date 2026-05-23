# Decision Log: SPC-00011 Etymology Chain Linking

## Starting Question

"Top-down (word -> parents) doesn't seem to work well, as the Wiktionary data is scattered around. Can we link up properly the whole chain? There are multiple meanings/etymologies for the same word as well."

## Investigation Process

### Phase 1: Codebase Analysis

Explored the full chain-building pipeline:
- `template_parser.py` extracts `args.2` (lang_code) and `args.3` (word) from ancestry templates
- `tree_builder.py` builds chains from templates, then expands descendants via `$elemMatch` queries
- Descendant search works template-to-template (no document lookup)
- But cognate expansion, mention edges, and node navigation all do document lookups using template-derived labels

### Phase 2: Database Investigation

Traced the "wine" chain through the DB:

| Ancestor | Template form | DB lookup | Result |
|---|---|---|---|
| Middle English "wyn" | `wyn` | `{word: "wyn", lang_code: "enm"}` | FOUND (2 docs) |
| Old English "wīn" | `wīn` | `{word: "wīn", lang_code: "ang"}` | NOT FOUND (DB has "win") |
| Proto-West Germanic "*wīn" | `*wīn` | `{word: "*wīn", lang_code: "gmw-pro"}` | NOT FOUND (no `*` prefix in DB) |
| Proto-Germanic "*wīną" | `*wīną` | `{word: "*wīną", lang_code: "gem-pro"}` | NOT FOUND (no `*` prefix in DB) |
| Latin "vīnum" | `vīnum` | `{word: "vīnum", lang_code: "la"}` | NOT FOUND (DB has "vinum") |

Key insight: the chain breaks at step 2 (Old English) due to macron mismatch, and all reconstructed languages fail due to asterisk prefix.

Verified that:
- Proto-Germanic words exist in DB (5,689 docs) but WITHOUT `*` prefix
- PIE words exist (1,808 docs) but WITHOUT `*` prefix
- Latin has 883K docs but WITHOUT macrons
- Old English has 62K docs but WITHOUT macrons

### Phase 3: Conflicting Ancestry Discovery

Latin "vinum" traces to PIE `*wéyh₁ō`, while English "wine" (via its templates) traces to PIE `*wóyh₁nom`. These are different ablaut grades of the same root — linguistically correct but causes graph fragmentation.

## Key Decisions

### Decision 1: Agile sprints over waterfall

**Rationale**: The problem scope is large (10.4M docs, multiple mismatch types). Iterative investigation lets us validate assumptions before committing to an implementation approach.

### Decision 2: DB sampling before raw JSONL inspection

**Rationale**: Tracing actual chains through the live DB gives immediate, concrete evidence of breakage patterns. Raw JSONL inspection can follow to check for unused fields.

### Decision 3: Try Wiktionary REST API for cross-referencing

**Rationale**: Wiktionary is the upstream source. Their API may reveal redirect/alias patterns that explain how template forms map to headwords. WebFetch got 403 on page scraping, but the MediaWiki API may work.

### Decision 4: Normalization is the clear Sprint 2 winner (from Sprint 1 data)

**Finding**: 90.4% of broken links are resolvable by two simple normalizations:
1. Strip leading `*` (46.2% of all refs — reconstructed language convention)
2. Unicode NFKD decomposition + strip combining marks (11.2% — macrons in OE, Latin)

**Implication**: Option A (query-time normalization) is strongly favored. No ETL re-run needed, fixes the vast majority of cases immediately. Option B/C are overkill for the measured problem.

**Open question for Sprint 2**: What to do about the 9.6% "missing entirely" — these are mostly PIE alternate forms. Options:
- Accept as phantom nodes (display-only, no clickable document)
- Try fuzzy matching against same lang_code with edit distance
- Create synthetic stub documents at ETL time from template data

### Decision 5: `etymology_number` solves polysemy

**Finding**: Kaikki includes `etymology_number` on every document. "bank" has entries numbered 1 (financial institution), 2 (river bank), 3 (row/panel). This is the Wiktionary section number.

**Implication**: Sprint 3 (polysemy) has a straightforward solution — use `etymology_number` as part of the document identity. Changes needed in `find_one` queries and potentially the node_id function.

### Decision 6: Centralized fallback lookup helper over scattered normalization

**Alternatives considered:**
1. Normalize at the API boundary (router level) — word arrives pre-normalized, all downstream code uses normalized form
2. Normalize inside each `find_one` call site independently
3. Centralized `_find_word_doc` helper on TreeBuilder + standalone function for routers

**Chosen**: Option 3.

**Rationale**:
- Option 1 loses the original template spelling for display (nodes would show `win` instead of `wīn`). Template labels are linguistically correct and should be preserved in the graph.
- Option 2 duplicates the exact-then-fallback logic in 5 places.
- Option 3 keeps one implementation of the fallback logic, preserves template-form labels for display, and only normalizes at the DB lookup boundary.

### Decision 7: Accept phantom nodes for the 9.6% "missing entirely"

**Alternatives considered:**
1. Fuzzy matching with edit distance against same `lang_code`
2. Synthetic stub documents created at ETL time from template data
3. Accept as display-only phantom nodes (no clickable document)

**Chosen**: Option 3.

**Rationale**:
- Fuzzy matching risks false positives (PIE words share many similar forms) and adds query complexity
- Synthetic stubs require ETL changes and create fake documents that could mislead users
- The frontend already handles 404s gracefully — "No details available" is accurate for these cases
- Most missing words are PIE alternate ablaut grades where no authoritative document exists
- Can revisit with synthetic stubs later if user demand warrants it

## Participants

- Human: identified the top-down linking issue, requested research
- Claude (DA): investigated codebase + database, traced chain breakage patterns, ran Sprint 1 audit
