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

## Participants

- Human: identified the top-down linking issue, requested research
- Claude (DA): investigated codebase + database, traced chain breakage patterns
