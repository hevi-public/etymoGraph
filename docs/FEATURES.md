# Etymology Explorer: Feature Documentation

*Last updated: January 30, 2026*

---

## Current State

The app is a fully functional local etymology explorer with interactive graph visualization. All MVP tasks (Phase 0 and Phase 1) are complete, plus several enhancements beyond the original plan.

### Data

- **Source**: Full multilingual Kaikki.org Wiktionary dump (`raw-wiktextract-data.jsonl.gz`)
- **Size**: ~10.4 million documents across all languages
- **Storage**: MongoDB with compound indexes for fast lookups
- **Indexes**:
  - `(word, lang)` — word lookup
  - `word` text index — search
  - `(etymology_templates.args.2, etymology_templates.args.3)` — descendant lookups

---

## Features

### 1. Search (Autocomplete)

- Text input in the header with prefix-based autocomplete
- Queries the API with 300ms debounce
- Dropdown shows matching words (up to 20)
- Click a suggestion or press Enter to load
- Clear button (×) resets to default word ("wine")
- Defaults to English language results

### 2. Etymology Tree Visualization

The core feature. Builds a full family tree for any word:

**Ancestor chain** — Traces the searched word back to its etymological root (e.g., PIE). Uses `etymology_templates` from the Kaikki data, chaining them sequentially (not flat).

**Descendant branches** — From each ancestor in the chain, finds all words that directly descend from it. This shows sibling languages branching off at each historical stage.

**Direct-parent filtering** — Only links a word to an ancestor if that ancestor is its immediate (first) parent in the etymology chain. Prevents spurious links where Kaikki data lists the full ancestry on every word.

**Parameters**:
- `max_ancestor_depth`: 10 (how far back to trace)
- `max_descendant_depth`: 1-5 (how many layers of descendants, default 3)
- `types`: Selectable connection types (see below)
- 50 descendants cap per node to prevent graph explosion

### 3. Connection Type Filter

Dropdown in the header ("Connections ▾") with checkboxes:

| Type | Meaning | Default |
|------|---------|---------|
| `inh` (Inherited) | Direct ancestor in the same language lineage | Checked |
| `bor` (Borrowed) | Loanword from another language | Unchecked |
| `der` (Derived) | General derivation | Unchecked |

Changing the filter re-fetches the tree immediately. Borrowed edges are shown with dashed lines.

### 4. Language Family Colors

Nodes are color-coded by language family:

| Family | Color | Languages |
|--------|-------|-----------|
| Germanic | Blue `#5B8DEF` | English, German, Norse, Dutch, Gothic, Yiddish, etc. |
| Romance | Red `#EF5B5B` | Latin, French, Spanish, Portuguese, Italian, etc. |
| Greek | Teal `#43D9A2` | Ancient Greek, Modern Greek |
| Slavic | Purple `#CE6BF0` | Russian, Polish, Czech, Serbian, etc. |
| Celtic | Orange `#FF8C42` | Irish, Welsh, Breton, etc. |
| Indo-Iranian | Pink `#FF6B9D` | Sanskrit, Hindi, Persian, etc. |
| Semitic | Cyan `#00BCD4` | Arabic, Hebrew, Aramaic, etc. |
| Uralic | Lime `#8BC34A` | Finnish, Hungarian, Estonian |
| PIE | Gold `#F5C842` | Proto-Indo-European |
| Other | Gray `#A0A0B8` | Everything else |

Legend displayed in the header.

### 5. Force-Directed Graph Layout

- Uses vis.js `forceAtlas2Based` physics solver
- Nodes spread out organically based on connections
- Draggable nodes — click and drag to rearrange
- Stabilizes after ~200 iterations

### 6. macOS Trackpad Support

Custom wheel event handling for natural trackpad behavior:

- **Two-finger scroll** → pans the graph (natural scroll direction)
- **Pinch** → zooms in/out (macOS sends `ctrlKey` for pinch gestures)
- vis.js built-in zoom is disabled to prevent conflicts

### 7. Zoom Controls

Three buttons in the bottom-right corner:

| Button | Action |
|--------|--------|
| ☆ | Focus on the searched word (level 0), zoom to scale 1.2 |
| ⊙ | Focus on the etymological root (deepest ancestor), zoom to scale 1.2 |
| ⊞ | Fit the entire graph in view |

All zoom actions animate over 500ms with easeInOutQuad easing. Focus buttons also select/highlight the target node.

### 8. Word Detail Panel

Click any node in the graph to open a side panel showing:

- **Word** and **language**
- **Part of speech** (noun, verb, etc.)
- **IPA pronunciation**
- **Definitions** (all glosses from all senses)
- **Etymology text** (human-readable narrative)

For words not in the database (e.g., ancestor language words not in the dump), shows an explanatory message. Close with × button.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/words/{word}?lang=English` | Full word data (definitions, pronunciation, etymology) |
| `GET /api/etymology/{word}/chain?lang=English` | Linear ancestry chain (word → root) |
| `GET /api/etymology/{word}/tree?lang=English&types=inh&max_descendant_depth=3` | Full family tree with branches |
| `GET /api/search?q=wine&limit=20` | Prefix search, deduplicated by word |
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
| Connection type filter | Toggle inherited/borrowed/derived with checkboxes |
| Direct-parent chain fix | Only link words to their immediate ancestor |
| Extended language colors | 10 language families with vibrant palette |
| macOS trackpad support | Pinch-to-zoom, two-finger pan |
| Zoom controls | Focus word, focus root, fit-all buttons |
| Force-directed layout | Organic graph layout instead of rigid hierarchy |

### Phase 2: Nice-to-Haves — NOT STARTED

| Task | Description | Status |
|------|-------------|--------|
| N2.1 | Cognate view (same PIE root) | Not started |
| N2.2 | Language family filter (show only Germanic, etc.) | Not started |
| N2.3 | Dark mode toggle | Not needed (app is already dark) |
| N2.4 | Shareable URLs (`/#/wine`) | Not started |
| N2.5 | Static export for GitHub Pages | Not started |
| N2.6 | Bulk export (top 1000 words) | Not started |
| N2.7 | Richer word details panel | Partially done (basic panel exists) |
| N2.8 | Performance (lazy-load, large graphs) | Partially done (descendant cap at 50) |

---

## Known Limitations

1. **Ancestor word details**: Words in ancestor languages (Old English, Proto-Germanic, etc.) may not have full entries in the Kaikki dump. The detail panel shows an explanatory message for these.

2. **Descendant cap**: Each node is limited to 50 descendants to prevent graph explosion. Some PIE roots have hundreds of descendants across all languages.

3. **Search is English-only**: The search endpoint filters by `lang: "English"`. Other languages can be explored by clicking through the graph.

4. **No URL routing**: Refreshing the page always loads "wine". No browser back/forward support.

5. **Edge labels overlap**: On dense graphs, "inherited"/"borrowed" labels can overlap and become hard to read.

---

*Stack: MongoDB + FastAPI + vis.js + Docker Compose*
