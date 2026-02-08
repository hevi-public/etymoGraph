# Etymology Explorer: Feature Documentation

*Last updated: February 8, 2026*

---

## Current State

The app is a fully functional local etymology explorer with interactive graph visualization. All MVP tasks (Phase 0 and Phase 1) are complete, plus several enhancements beyond the original plan.

### Data

- **Source**: Full multilingual Kaikki.org Wiktionary dump (`raw-wiktextract-data.jsonl.gz`)
- **Size**: ~10.4 million documents across all languages
- **Storage**: MongoDB with compound indexes for fast lookups
- **Indexes**:
  - `(word, lang)` — word lookup
  - `word` — prefix search (case-sensitive regex)
  - `word` text index — full-text search
  - `(etymology_templates.args.2, etymology_templates.args.3)` — descendant lookups
  - `(etymology_templates.name, etymology_templates.args.2, etymology_templates.args.3)` — typed descendant lookups
- **Auxiliary collections**:
  - `languages` — precomputed lang_code ↔ lang name mapping (~4,760 entries), built at ETL time

---

## Features

### 1. Search (Autocomplete)

- Text input in the header with prefix-based autocomplete
- Queries the API with 300ms debounce
- Dropdown shows matching words (up to 20)
- Exact case-sensitive matches are prioritized over prefix matches (e.g., "key" ranks above "Key")
- Prefix search is case-sensitive to enable MongoDB index usage (fast even on 10.4M docs)
- Click a suggestion or press Enter to load
- Clear button (×) resets to default word ("wine")
- Suggestions show word and language (language dimmed), e.g., "asztal (Hungarian)"
- Clicking a suggestion or pressing Enter passes the correct language to the graph
- If no language is provided (e.g., direct call), auto-detects via search API lookup
- Multilingual: searches across all languages in the database

### 2. Etymology Tree Visualization

The core feature. Builds a full family tree for any word:

**Ancestor chain** — Traces the searched word back to its etymological root (e.g., PIE). Uses `etymology_templates` from the Kaikki data, chaining them sequentially (not flat).

**Descendant branches** — From each ancestor in the chain, finds all words that directly descend from it. This shows sibling languages branching off at each historical stage.

**Direct-parent filtering** — Only links a word to an ancestor if that ancestor is its immediate (first) parent in the etymology chain. Prevents spurious links where Kaikki data lists the full ancestry on every word.

**Cognate expansion** — When cognates are enabled, each cognate's full ancestry and descendant tree is also expanded (up to 2 rounds). This means searching "busz" (Hungarian) with cognates shows not just English/German/French "bus", but also all the languages that borrowed from English "bus" (Japanese, Welsh, Arabic, etc.).

**Language code mapping** — Language codes (e.g., "hu" → "Hungarian") are resolved dynamically from a precomputed `languages` collection in MongoDB, covering all ~4,760 languages in the dataset. No hardcoded mapping.

**Parameters**:
- `max_ancestor_depth`: 10 (how far back to trace)
- `max_descendant_depth`: 1-5 (how many layers of descendants, default 3)
- `types`: Selectable connection types (see below)
- 50 descendants cap per node to prevent graph explosion

### 3. Connection Type Filter

Checkboxes in the Filters popover (click "Filters ▾" button in header):

| Type | Meaning | Default |
|------|---------|---------|
| `inh` (Inherited) | Direct ancestor in the same language lineage | Checked |
| `bor` (Borrowed) | Loanword from another language | Checked |
| `der` (Derived) | General derivation | Checked |
| `cog` (Cognate) | Related word from the same root in another language | Checked |

Changing the filter re-fetches the tree immediately. Borrowed edges are shown with dashed lines. Cognate edges are shown with gold dashed lines.

**Automatic edge types** (not user-selectable, shown when a word has no ancestry):

| Type | Meaning | Source Templates | Style |
|------|---------|------------------|-------|
| `component` | Morphological component of the word (base word in a derivation) | `af`, `affix`, `suffix`, `prefix`, `compound`, `blend` | Gray dashed |
| `mention` | Word mentioned in etymology text but not as an ancestor | `m`, `m+`, `l` | Gray dashed |

These appear automatically for words with uncertain/disputed etymologies that lack standard ancestry templates. For example, "piros" (Hungarian) has no `inh`/`bor`/`der` ancestors, but the `af` template indicates it's formed from "pirít" + "-os", so a `component` edge connects them.

### 4. Language Family Colors

Nodes are color-coded by language family. The legend is dynamically generated from a single source of truth in `graph.js`.

| Family | Color | Key Languages |
|--------|-------|---------------|
| Germanic | Blue `#5B8DEF` | English, German, Norse, Dutch, Gothic, Yiddish, Swedish, etc. |
| Romance | Red `#EF5B5B` | Latin, French, Spanish, Portuguese, Italian, Romanian, etc. |
| Greek | Teal `#43D9A2` | Ancient Greek, Modern Greek |
| PIE | Gold `#F5C842` | Proto-Indo-European |
| Slavic | Purple `#CE6BF0` | Russian, Polish, Czech, Serbian, Ukrainian, etc. |
| Celtic | Orange `#FF8C42` | Irish, Welsh, Breton, Cornish, Gaulish, etc. |
| Indo-Iranian | Pink `#FF6B9D` | Sanskrit, Hindi, Persian, Urdu, Kurdish, etc. |
| Semitic | Cyan `#00BCD4` | Arabic, Hebrew, Aramaic, Akkadian, Amharic, etc. |
| Uralic | Lime `#8BC34A` | Finnish, Hungarian, Estonian, Sami, etc. |
| Baltic | Amber `#FFC107` | Lithuanian, Latvian, Old Prussian |
| Turkic | Violet `#673AB7` | Turkish, Azerbaijani, Kazakh, Uzbek, etc. |
| Sino-Tibetan | Deep Purple `#9C27B0` | Chinese, Mandarin, Cantonese, Tibetan, Burmese |
| Austronesian | Bright Blue `#2196F3` | Indonesian, Malay, Tagalog, Hawaiian, Maori, etc. |
| Japonic | Pink-Red `#E91E63` | Japanese, Okinawan, Ryukyuan |
| Koreanic | Blue-Gray `#607D8B` | Korean, Jeju |
| Bantu | Brown `#795548` | Swahili, Zulu, Xhosa, Yoruba, etc. |
| Dravidian | Dark Teal `#009688` | Tamil, Telugu, Malayalam, Kannada |
| Kartvelian | Green `#4CAF50` | Georgian, Mingrelian, Svan |
| Armenian | Deep Orange `#FF5722` | Armenian, Classical Armenian |
| Albanian | Yellow-Lime `#CDDC39` | Albanian, Gheg, Tosk |
| Other | Gray `#A0A0B8` | Everything else |

The expanded 20-family palette is data-driven, based on actual database distribution analysis showing 18K+ Proto-Turkic references, 16K+ Proto-Austronesian, 10K+ Sino-Tibetan, etc. Legend is displayed as a semi-transparent overlay in the bottom-left corner of the graph canvas (fades to full opacity on hover).

### 5. Pluggable Layout Engine

The graph layout is a pluggable strategy system. A `LAYOUTS` registry maps layout names to strategy objects, each providing `getGraphOptions()`, `buildVisNodes()`, `buildExtraEdges()`, `getInitialView()`, and an optional `onBeforeDrawing` canvas hook. Shared vis.js options are extracted into `baseGraphOptions()` so each strategy only overrides what differs. Language family classification uses a single `LANG_FAMILIES` source of truth for both color and family name. A `<select>` dropdown in the Filters popover lets users switch layouts; the preference is persisted in `localStorage`.

**Deterministic layout**: The graph uses a fixed random seed (`randomSeed: 42`) in the vis.js layout configuration, ensuring the physics simulation produces consistent, reproducible layouts every time for the same word and connection settings.

**Built-in layouts:**

#### Force-Directed
- Root node pinned at (0,0) with mass 5, exponential mass decay per level
- Global fallback: `gravitationalConstant: -200`, `centralGravity: 0.005`, `springConstant: 0.04`, `damping: 0.6`, `avoidOverlap: 0.5`
- Per-edge `length` and `springConstant` override globals via log-degree scaling
- No extra edges, no canvas drawing
- Initial view at (0,0) scale 1

**Radial initial positioning:** Etymology graphs start in a radial fan layout (concentric rings from root) instead of a linear tree, matching the shape that forceAtlas2Based converges to. This reduces physics stabilization time from 2-5 seconds of rearranging to a quick fine-tune. The radial layout assigns angular spans proportional to subtree size, normalized to a full 2π circle.

**Barycentric refinement:** After the initial tree-based layout (radial or linear), 3 passes of barycentric refinement shift each non-root node 50% toward the average position of all its neighbors across ALL edges (not just the spanning tree). This accounts for the ~30-50% of edges (cognates, borrowings, mentions) that the BFS spanning tree ignores.

#### Era Layers
- Fixed Y positions per era tier; initial X positions cluster nodes by language family, then physics fine-tunes
- 8 horizontal era bands from oldest (bottom) to newest (top):

| Tier | Era | Example Languages |
|------|-----|-------------------|
| 0 | Deep Proto (~4000+ BCE) | Proto-Indo-European, Proto-Uralic |
| 1 | Branch Proto (~2000–500 BCE) | Proto-Germanic, Proto-Italic, Proto-Slavic |
| 2 | Classical/Ancient (~500 BCE–500 CE) | Latin, Ancient Greek, Sanskrit, Gothic |
| 3 | Early Medieval (~500–1000 CE) | Old English, Old Norse, Old French |
| 4 | Late Medieval (~1000–1500 CE) | Middle English, Middle French, Anglo-Norman |
| 5 | Early Modern (~1500–1700 CE) | Early Modern English |
| 6 | Modern (~1700–present) | English, French, German, Finnish (default) |
| 7 | Contemporary | Reserved for neologisms |

- Language classification uses prefix matching: `Proto-Indo-European` → tier 0, other `Proto-*` → tier 1, `Old *` → tier 3, etc.
- Invisible family-clustering spring edges between same-family nodes in the same tier
- Era bands drawn as subtle alternating backgrounds with labels on the left margin
- Initial view centered on the searched word's era tier

**Adding a new layout:** Add an entry to the `LAYOUTS` object in `graph.js` conforming to the strategy interface. It will automatically appear in the dropdown.

**Connection-based edge length/strength:** Edge rest length and spring constant are computed per-edge based on endpoint node degree (number of connections), using a log2 scaling:

```
length        = BASE_LENGTH + LENGTH_SCALE * log2(1 + dFrom + dTo)    // BASE_LENGTH=180, LENGTH_SCALE=80
springConstant = BASE_SPRING / log2(1 + maxDeg)                        // BASE_SPRING=0.08
```

This spreads dense clusters apart (more connections → longer, weaker springs) while pulling peripheral nodes closer (fewer connections → shorter, stronger springs). The logarithmic curve ensures diminishing returns — going from 1 to 5 connections has more visual impact than going from 20 to 25. Applied to both the etymology graph (`buildVisEdges`) and concept map (`buildConceptEdges`).

**Degree-based edge opacity:** Edges between high-degree nodes fade to reduce visual clutter in dense areas, while peripheral edges stay vivid. Opacity is computed as `max(0.2, 1.0 / log2(2 + maxDeg))`, giving hub edges ~20% opacity and peripheral edges ~63%. On node click, hop-based brightness multiplies with degree opacity for compound fading. Highlight colors remain bright.

**Dense-area label hiding:** When both endpoints of an edge have degree > 5, the edge label is hidden (they overlap and are unreadable in dense clusters). Edge type is still conveyed by line style (solid vs dashed) and color (gold for cognate, grey for mention).

### 6. macOS Trackpad Support

Custom wheel event handling for natural trackpad behavior:

- **Two-finger scroll** → pans the graph (natural scroll direction), speed scaled by zoom level so panning feels consistent when zoomed in
- **Pinch** → zooms in/out (macOS sends `ctrlKey` for pinch gestures)
- vis.js built-in zoom is disabled to prevent conflicts

### 7. Zoom Controls

Four buttons in the top-right corner:

| Button | Action |
|--------|--------|
| ☰ | Toggle the detail panel open/closed |
| ☆ | Focus on the searched word (level 0), zoom to scale 2.5 |
| ⊙ | Focus on the etymological root (deepest ancestor), zoom to scale 2.5 |
| ⊞ | Fit the entire graph in view |

All zoom actions animate over 500ms with easeInOutQuad easing. Focus buttons also select/highlight the target node.

### 8. Word Detail Panel

Click any node in the graph to open a side panel showing:

- **Word** and **language**
- **Part of speech** (noun, verb, etc.)
- **IPA pronunciation**
- **Wiktionary link** — opens the word's Wiktionary page in a new tab. Uses `Reconstruction:` prefix for proto-languages (e.g., Proto-Italic/wīnom) and `#Language` anchors for regular words
- **Definitions** (all glosses from all senses)
- **Etymology text** (human-readable narrative) — words mentioned in the etymology chain, prose, and cognates are clickable links when they match known `etymology_templates`. A link-mode toggle next to the "Etymology" heading lets users choose between **In-app** (loads the word in the graph via `selectWord()`) and **Wiktionary** (opens a new tab). Preference is persisted in `localStorage`.
- **Connections** — grouped by type (Inherited, Borrowed, Derived, Cognate) with clickable links that select and pan to the target node

For words not in the database (e.g., ancestor language words not in the dump), shows an explanatory message. Close with × button.

### 9. Distance-Based Opacity

Clicking a node highlights it and fades distant nodes by graph hop distance:

| Hops | Opacity |
|------|---------|
| 0 (selected) | 100% |
| 1 | 90% |
| 2 | 50% |
| 3+ | 10% |

Both node background and text fade together. Clicking empty space resets all nodes to full opacity.

### 10. Click-to-Center

Clicking any node smoothly animates it to the center of the viewport (400ms easeInOutQuad).

### 11. Uncertain Etymology Detection

Words with disputed, uncertain, or unknown etymologies are now detected and displayed distinctly.

**Detection methods:**

| Source | Signal Type | Confidence |
|--------|-------------|------------|
| `unk` template | Unknown origin | High |
| `unc` template | Uncertain origin | High |
| Text: "disputed", "competing etymologies" | Disputed | Medium |
| Text: "uncertain origin", "possibly from" | Uncertain | Medium |

**Uncertainty types:**

| Type | Description | Badge Color |
|------|-------------|-------------|
| `unknown` | Origin is completely unknown | Red |
| `uncertain` | Origin is unclear or speculative | Yellow |
| `disputed` | Multiple competing theories exist | Purple |

**Visual indicators:**

- **Graph nodes**: Dashed border (`borderDashes: [5, 5]`) and desaturated color for uncertain nodes
- **Root node**: The deepest ancestor (etymological root) is visually prominent with a gold border, gold glow shadow, and larger text/padding — identifiable at a glance in both layouts
- **Detail panel**: Colored badge showing uncertainty type and confidence level

**API response** (from `/api/words/{word}`):
```json
{
  "etymology_uncertainty": {
    "is_uncertain": true,
    "type": "disputed",
    "source": "text:two interpretations",
    "confidence": "medium"
  },
  "related_mentions": [
    {"word": "pirít", "lang": "Hungarian", "lang_code": "hu", "source_template": "m", "role": "mention"}
  ]
}
```

**Examples:**
- "girl" (English) → `unknown` (has `unk` template)
- "dog" (English) → `uncertain` (has `unc` template)
- "piros" (Hungarian) → `disputed` (text mentions "two interpretations")

### 12. Concept Map (Phonetic Similarity Visualization)

A sibling view to the etymology graph that answers: "What do languages call this concept, and which ones sound similar?"

**How it works:**
1. User enters a concept (e.g., "fire", "water", "hand")
2. The system finds all words across languages that express that concept (via Wiktionary translation hubs + gloss fallback)
3. Pairwise phonetic similarity is computed using Dolgopolsky consonant sound classes
4. Words are displayed as a force-directed graph where proximity = phonetic similarity

**Data pipeline:**
- **Precomputation**: `make precompute-phonetic` runs a batch script that enriches all entries with IPA data with a `phonetic` subdocument containing Dolgopolsky classes (requires `lingpy` + `pymongo` installed locally)
- **Phonetic subdocument structure**: `{ipa, dolgo_classes, dolgo_consonants, dolgo_first2, tokens}`
- **LingPy is only needed for precomputation** — runtime similarity is pure string comparison

**Concept resolution strategies:**
- **Strategy A (Translation Hub)**: Queries the English entry's `translations` array, then batch-looks up each translated word in the database for phonetic data. Most reliable.
- **Strategy B (Gloss Search)**: Searches `senses.glosses` for exact concept match across all entries. Noisier, used as fallback when hub gives < 10 results.
- **Combined**: When hub is sparse, merges both strategies. Resolution method is returned in the API response.

**Phonetic similarity:**
- Uses **Dolgopolsky consonant classes** — IPA is tokenized into sound classes, vowels are stripped, leaving a consonant skeleton
- **Distance metric**: Normalized Levenshtein distance on consonant class strings (0.0 = identical, 1.0 = completely different)
- **Turchin match**: Binary check — do the first two consonant classes match? Classic cognate detection method.
- **Edges**: All pairs with similarity >= 0.3 (floor) or Turchin match are returned; frontend filters further via slider

**Clustering:**
- Words are grouped by their first two Dolgopolsky consonant classes (Turchin clusters)
- Example: "fire" produces K-N group (ignis, agni, ugnis), P-R group (fire, Feuer, vuur, pyr), T-S group (tuz, tuli)

**Frontend controls:**
- **View toggle**: Tab-like buttons in header switch between Etymology Graph and Concept Map
- **Concept search**: Debounced autocomplete with translation count hints (in header)
- **Similarity slider**: In Filters popover; adjusts the similarity threshold (0.0–1.0); filters edges client-side without re-calling API
- **Etymology edges checkbox**: In Filters popover; toggles overlay of known etymological connections (solid arrows vs dashed phonetic edges)
- **POS filter**: In Filters popover; radio buttons for All / Noun / Verb / Adj

**Graph physics:**
- Uses `barnesHut` solver (separate from etymology graph's `forceAtlas2Based`)
- High repulsion (`gravitationalConstant: -8000`) to spread nodes apart despite dense edge network
- Very weak spring pull (`springConstant: 0.005`) so edges suggest proximity without forcing tight clusters
- Physics disables automatically after the graph settles (`stabilized` event), producing a static layout
- Etymology graph keeps its own continuous `forceAtlas2Based` physics — the two views have independent configurations

**Node styling:**
- Colored by language family (same 20-family palette as etymology graph)
- Dashed grey edges = phonetic similarity (width + opacity proportional to score)
- Solid dark edges = etymological connections (arrows)
- Click a node to show detail panel + "View in Etymology Graph" button

**API endpoints:**
- `GET /api/concept-map?concept=fire&pos=noun&max_words=200` — returns words, phonetic_edges, etymology_edges, clusters
- `GET /api/concepts/suggest?q=fi&limit=10` — autocomplete for concept search
- `GET /api/words/{word}?lang=English` — now includes `phonetic_ipa`, `dolgo_classes`, `dolgo_consonants`

### 13. Related Mention Edges

For words that have no standard ancestry (inh/bor/der templates), the graph now shows edges to related words extracted from other etymology templates (`af`, `m`, `m+`, `l`). This is particularly useful for words with uncertain/disputed etymologies that still have known morphological components.

**Edge types:**

| Type | Meaning | Style |
|------|---------|-------|
| `component` | Word is a morphological component (from `af` template) | Gray dashed |
| `mention` | Word is mentioned in etymology (from `m`/`m+`/`l` templates) | Gray dashed |

**Example:**
- "piros" (Hungarian) has a disputed etymology with no standard ancestry, but the `af` template shows it's derived from "pirít" + "-os" suffix. The graph now shows a gray dashed "component" edge from "pirít" to "piros".

**Detail panel:**
The connections panel shows "Component" and "Related" sections for these edge types.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/words/{word}?lang=English` | Full word data (definitions, pronunciation, etymology, uncertainty info, related mentions) |
| `GET /api/etymology/{word}/chain?lang=English` | Linear ancestry chain (word → root) |
| `GET /api/etymology/{word}/tree?lang=English&types=inh&max_descendant_depth=3` | Full family tree with branches (nodes include uncertainty metadata) |
| `GET /api/search?q=wine&limit=20` | Prefix search, deduplicated by word |
| `GET /api/concept-map?concept=fire&pos=noun&max_words=200` | Concept map with phonetic similarity edges, etymology edges, and clusters |
| `GET /api/concepts/suggest?q=fi&limit=10` | Concept autocomplete (English entries with translations) |
| `GET /docs` | Swagger UI (auto-generated) |

---

## Automation

| Command | Action |
|---------|--------|
| `make setup` | Build + download + load (first time) |
| `make run` | Start all services |
| `make stop` | Stop all services |
| `make update` | Force re-download data + reload into MongoDB |
| `make download` | Download data (skip if exists) |
| `make load` | Load data into MongoDB |
| `make precompute-phonetic` | Precompute Dolgopolsky sound classes for concept map (requires `lingpy` + `pymongo`) |
| `make logs` | Tail all service logs |
| `make clean` | Remove containers and data |
| `./scripts/init.sh` | Check prerequisites, create dirs, build images |
| `./scripts/download-data.sh` | Download dump (skip if exists) |
| `./scripts/download-data.sh --force` | Force re-download |

---

## Implementation Plan Status

### Phase 0: Prototype — COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| P0.1 | Docker + vis.js setup | Done |
| P0.2 | Static search with hardcoded words | Done |

### Phase 1: MVP — COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| M1.1 | MongoDB container | Done |
| M1.2 | Download Kaikki data | Done |
| M1.3 | Load data into MongoDB | Done |
| M1.4 | FastAPI setup | Done |
| M1.5 | Word lookup API | Done |
| M1.6 | Etymology chain API | Done |
| M1.7 | Search API | Done |
| M1.8 | Connect frontend to API | Done |
| M1.9 | Graph polish | Done |
| M1.10 | Automation (Makefile, README) | Done |

### Beyond Plan (Completed)

| Feature | Description |
|---------|-------------|
| Full multilingual dump | Switched from English-only to full Wiktionary data (10.4M docs) |
| Etymology tree with descendants | Reverse lookup to build full language family trees |
| Connection type filter | Toggle inherited/borrowed/derived/cognate with checkboxes (all on by default) |
| Direct-parent chain fix | Only link words to their immediate ancestor |
| Extended language colors | 20 language families with data-driven palette + dynamic legend |
| macOS trackpad support | Pinch-to-zoom, two-finger pan with zoom-scaled panning speed |
| Zoom controls | Panel toggle, focus word, focus root, fit-all buttons (top-right) |
| Era-layered layout | Vertically layered by historical era with horizontal self-organization |
| Cognate view | Cognate edges as gold dashed lines, toggleable via filter, recursive expansion |
| Root node prominence | Gold border, glow shadow, and larger text on the etymological root node |
| Distance-based opacity | Clicked node at full opacity, fading by hop distance |
| Click-to-center | Clicked nodes animate to viewport center |
| Clickable connections panel | Detail panel shows connections grouped by type with clickable links |
| Startup race fix | Backend healthcheck + frontend depends_on prevents nginx failure |
| Search performance | Case-sensitive prefix regex to use index, single-field word index |
| Dynamic lang mapping | Language code ↔ name from DB instead of hardcoded map (~4,760 languages) |
| Recursive cognate expansion | Cognate nodes get their own ancestry + descendants expanded (2 rounds) |
| Etymology link mode toggle | Chain/prose/cognate words are clickable; in-app or Wiktionary mode with localStorage persistence |
| Detail panel toggle | ☰ button in zoom controls to reopen closed detail panel |
| Zoom-scaled panning | Two-finger pan speed scales with zoom level for consistent feel |
| Physics tuning | Softer repulsion (-80), weak central gravity (0.005), stiffer springs for horizontal stability within era bands |
| Pluggable layout engine | Layout strategies as pluggable objects with registry, dropdown selector, localStorage persistence |
| Chain endpoint direction fix | Fixed `/chain` edge direction (now ancestor→descendant) and level signs (now negative for ancestors) |
| Cognate-only filter fix | Fixed `?types=cog` requests being incorrectly ignored and defaulting to `inh` |
| Uncertain etymology detection | Classify and display words with unknown, uncertain, or disputed etymologies |
| Related mention edges | Words without ancestry show edges to related words from `af`/`m`/`m+`/`l` templates |
| Deterministic layout | Fixed random seed for reproducible graph layouts |
| Concept Map | Phonetic similarity visualization for semantic fields using Dolgopolsky classes |
| Compact header | Slimmed to single row: title, view toggle, search, filters popover. Legend moved to graph overlay. |
| Connection-based edge length | Per-edge length and spring constant scaled by log2(degree) of endpoint nodes — dense clusters spread out, peripheral nodes pull closer |
| Dense cluster readability | Stronger physics separation (repulsion -200, avoidOverlap 0.5), degree-based edge opacity fading, label hiding in dense areas |

### Concept Map (Phonetic Similarity Visualization)

| Task | Description | Status |
|------|-------------|--------|
| CM.1 | Precompute Dolgopolsky sound classes for IPA entries | Done (backend/etl/precompute_phonetic.py) |
| CM.2 | Phonetic similarity service (distance, edges, clusters) | Done |
| CM.3 | Concept resolver service (translation hub + gloss fallback) | Done |
| CM.4 | Concept map API endpoints (/api/concept-map, /api/concepts/suggest) | Done |
| CM.5 | Augment /api/words/{word} with phonetic fields | Done |
| CM.6 | Frontend: view toggle, concept search, concept-map.js | Done |
| CM.7 | Frontend: similarity slider, etymology edges toggle, POS filter | Done |
| CM.8 | Unit tests for phonetic similarity and concept resolver | Done |
| CM.9 | Cluster convex hulls (Phase 3) | Not started |
| CM.10 | "Highlight unknown origins" toggle (Phase 3) | Not started |

### Phase 2: Nice-to-Haves — IN PROGRESS

| Task | Description | Status |
|------|-------------|--------|
| N2.1 | Cognate view (same PIE root) | Done |
| N2.2 | Language family filter (show only Germanic, etc.) | Not started |
| N2.3 | Dark mode toggle | Not needed (app is already dark) |
| N2.4 | Shareable URLs (`/#/wine`) | Not started |
| N2.5 | Static export for GitHub Pages | Not started |
| N2.6 | Bulk export (top 1000 words) | Not started |
| N2.7 | Richer word details panel | Done (connections, definitions, etymology) |
| N2.8 | Performance (lazy-load, large graphs) | Partially done (descendant cap at 50) |

---

## Development & Code Quality

### Coding Standards

**Status**: Comprehensive coding standards implemented with automated enforcement.

**Documentation**: `docs/CODING_STANDARDS.md` defines all standards for Python, JavaScript, documentation, testing, and git workflow.

**Key standards**:
- **Python**: Type hints + Google-style docstrings for all functions, error handling at system boundaries, async/await patterns
- **JavaScript**: Small pure functions (<80 lines), JSDoc for complex functions, error handling for API calls
- **General**: Extract logic into focused functions, contextual comments explaining *why*, no over-engineering
- **Testing**: pytest for services layer and utilities with complex logic
- **Documentation**: Update FEATURES.md before committing feature changes

**Enforcement**:
- **Pre-commit hooks**: Ruff (Python linting + formatting) + ESLint (JavaScript) block commits with violations
- **Code review**: Review Agent enforces standards during PR review (MUST level for violations)
- **Migration strategy**: All new code follows standards immediately; existing code refactored opportunistically

**Development commands**:
```bash
make setup-dev  # Install linters, pre-commit hooks, test dependencies
make lint       # Run Ruff and ESLint
make format     # Format Python code with Ruff
make test       # Run pytest
```

**Test coverage**:
- `test_tree_builder.py`: TreeBuilder service tests (some TODOs require test database)
- `test_etymology_classifier.py`: Full coverage of uncertainty detection and word mention extraction
- Future: tests for other services (template_parser, lang_cache) when touched

**Linting configuration**:
- `pyproject.toml`: Ruff configuration (line length 100, Python 3.11 target, comprehensive rule set)
- `.eslintrc.json`: ESLint configuration (double quotes, 4-space indent, semicolons)
- `.pre-commit-config.yaml`: Pre-commit hook configuration

---

## Known Limitations

1. **Ancestor word details**: Words in ancestor languages (Old English, Proto-Germanic, etc.) may not have full entries in the Kaikki dump. The detail panel shows an explanatory message for these.

2. **Descendant cap**: Each node is limited to 50 descendants to prevent graph explosion. Some PIE roots have hundreds of descendants across all languages.

3. **Search prefix matching**: Search uses case-sensitive prefix regex for performance. Lowercase queries won't match capitalized words (use exact match for that).

4. **No URL routing**: Refreshing the page always loads "wine". No browser back/forward support.

5. **Edge labels hidden in dense areas**: When both endpoints have degree > 5, edge labels are auto-hidden. Edge type is still conveyed by line style and color.

6. **Uncertainty detection is pattern-based**: The system detects uncertainty through template markers (`unk`, `unc`) and text patterns. Some uncertain etymologies may not be detected if they use unusual phrasing, and false positives are possible with text pattern matching.

7. **Concept map requires precomputation**: The `phonetic` subdocument must be precomputed before the concept map works. Run `make precompute-phonetic` (requires `lingpy` and `pymongo` installed locally, outside Docker).

8. **Concept map coverage**: Only ~31.7% of entries have IPA data. Translation hub entries without IPA pronunciation in the database won't appear on the concept map.

9. **Pairwise similarity is O(N^2)**: For concepts with many translations (200+ words), the similarity computation involves up to 20K comparisons. This is fast for short strings but could be slow for very large concept maps.

---

*Stack: MongoDB + FastAPI + vis.js + Docker Compose*
