# SPC-00003: Shareable Links — History API URL Routing

| Field | Value |
|---|---|
| **Status** | approved |
| **Created** | 2026-02-09 |
| **Modifies** | SPC-00002 (adds URL routing for concept map state) |
| **Modified-by** | — |

---

**Context:** Etymology Explorer is a single-page application with two views (Etymology Graph and Concept Map), each with distinct navigable state. Currently all state lives in JS globals and is lost on refresh. The URL bar always shows `/`. This feature adds browser-native URL routing so users can share, bookmark, and navigate with back/forward.

---

## 1. Purpose

Shareable Links adds URL-based state management to Etymology Explorer so that:

1. The browser URL reflects what the user is currently viewing
2. Copying and sharing a URL reconstructs the exact view (word, language, filters, active graph)
3. Browser back/forward buttons navigate between primary actions (word changes, view switches)
4. Page refresh restores the current state instead of resetting to "wine"

This is a **foundation feature** — the router is designed to be view-scoped and extensible, so future views and parameters can be added without modifying router internals.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (vanilla JS)                  │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │
│  │ router.js   │  │ app.js     │  │ graph.js /         │ │
│  │ (NEW)       │←→│ (modified) │←→│ concept-map.js     │ │
│  │             │  │            │  │ search.js           │ │
│  │ VIEW_PARAMS │  │ selectWord │  │ (minimal changes)  │ │
│  │ push/replace│  │ switchView │  │                    │ │
│  │ popstate    │  │ loadConcept│  │                    │ │
│  └─────┬──────┘  └────────────┘  └────────────────────┘ │
│        │                                                  │
│        ▼                                                  │
│  window.history (pushState / replaceState / popstate)     │
│  URL: /?word=fire&lang=Latin                              │
│  URL: /?view=concept&concept=water&similarity=75          │
└──────────────────────────────────────────────────────────┘
```

The router is a **pure state↔URL sync layer**. It does not call app functions directly. Instead:
- App functions (selectWord, loadConceptMap, switchView) call `router.push()` or `router.replace()` after completing their work
- On popstate (back/forward), the router invokes a callback registered by app.js, which then calls the appropriate app functions to restore state

---

## 3. URL Format

Query parameters on root path. Each view's params are **scoped** — etymology params don't appear in concept URLs and vice versa. Default values are omitted for clean URLs.

**Examples:**

```
/                                              → wine, English, etymology (all defaults)
/?word=fire&lang=Latin                         → etymology: fire in Latin
/?view=concept&concept=water                   → concept map: "water"
/?view=concept&concept=fire&similarity=75      → concept map: 75% similarity
/?word=dog&types=inh,bor&layout=force-directed → etymology: custom filters
/?view=concept&concept=water&highlight=víz:Hungarian  → concept map with node highlighted (future)
```

---

## 4. Router Design: View-Scoped Parameter Registry

### 4.1 Parameter Definitions

The core data structure. Each view owns its params with defaults and optional parsers:

```javascript
const VIEW_PARAMS = {
  etymology: {
    word:   { default: "wine" },
    lang:   { default: "English" },
    types:  { default: "inh,bor,der" },
    layout: { default: "era-layered" },
  },
  concept: {
    concept:    { default: "" },
    pos:        { default: "" },
    similarity: { default: 100, parse: Number },
    etymEdges:  { default: true, parse: v => v !== "false" },
    // Future: highlight: { default: "" }
  },
};
const DEFAULT_VIEW = "etymology";
```

**Expandability:**
- Adding a new view (e.g., a future "Phonetic Map") = add entry to `VIEW_PARAMS`
- Adding a param to an existing view = add entry to that view's params object
- No changes to router core functions needed for either case

### 4.2 URL Building (internal)

`buildURL(state)` serializes state to a query string:

1. Read `state.view` — if it equals `DEFAULT_VIEW`, omit from URL
2. Look up `VIEW_PARAMS[state.view]` to get the param definitions for this view
3. For each param, compare against its default — only write non-default values
4. Return the query string (or empty string if all defaults)

### 4.3 URL Parsing (internal)

`parseURL()` deserializes the current URL:

1. Read `?view=X` from `URLSearchParams` — default to `DEFAULT_VIEW` if absent
2. Look up `VIEW_PARAMS[X]` — if unknown view, fall back to default view with default params
3. For each param definition, read from URL or use default. Apply `parse` function if defined
4. Return `{ view, ...params }`

---

## 5. Router Public API

`router.js` exposes a global `router` object (~100 lines):

```
router.initialize()          — parse URL, replaceState to normalize, attach popstate listener
router.onNavigate(callback)  — register callback for popstate events (back/forward)
router.push(params)          — merge partial params with current state → pushState
router.replace(params)       — merge partial params with current state → replaceState
router.state()               — returns current { view, ...viewParams } from internal cache
```

### 5.1 push() Behavior

1. Merge incoming partial params with current cached state
2. If `params.view` changes, fill in defaults for the new view (don't carry stale params from the old view)
3. Build URL from merged state
4. Compare new URL with current URL — **skip pushState if identical** (prevents duplicate history entries)
5. Call `window.history.pushState(mergedState, "", newURL)`
6. Update internal cache

### 5.2 replace() Behavior

Same as push() but calls `replaceState` instead. Used for filter adjustments that shouldn't create history entries.

### 5.3 initialize() Behavior

1. Parse current URL into state
2. Store in internal cache
3. Call `window.history.replaceState(state, "", buildURL(state))` to normalize the URL (ensures clean defaults)
4. Attach `popstate` event listener that:
   - Reads `event.state` (or falls back to `parseURL()`)
   - Updates internal cache
   - Invokes the callback registered via `onNavigate()`

---

## 6. pushState vs replaceState Strategy

| User Action | History Method | Rationale |
|---|---|---|
| Search for a new word (`selectWord`) | **pushState** | Primary navigation — back button should undo |
| Switch between Etymology ↔ Concept view | **pushState** | Major context change |
| Load a new concept (`loadConceptMap`) | **pushState** | Primary navigation |
| Cross-view nav ("View in Etymology/Concept Graph") | **pushState** (single entry) | One entry for the combined view switch + target word/concept |
| Adjust connection type checkboxes | **replaceState** | Filter tuning — don't pollute history |
| Change graph layout | **replaceState** | Filter tuning |
| Adjust similarity slider | **replaceState** | Filter tuning |
| Change POS radio filter | **replaceState** | Filter tuning |
| Toggle etymology edges checkbox | **replaceState** | Filter tuning |

**Why this split:** Back/forward should move between "places" (different words, different concepts, different views), not through every slider tick. Filters refine the current place — they modify the URL via replaceState so it's still shareable, but they don't add history entries.

---

## 7. Integration with Existing Code

### 7.1 Files to Change

| File | Change Scope | Description |
|---|---|---|
| `frontend/public/js/router.js` | **NEW** (~100 lines) | View-scoped router module |
| `frontend/public/index.html` | **1 line** | Add `<script src="js/router.js">` before app.js |
| `frontend/public/js/app.js` | **Major** | skipRoute params, updateDOMFromState, router init |
| `frontend/public/js/concept-map.js` | **1 line** | skipRoute on "View in Etymology" cross-nav |
| `frontend/public/js/search.js` | **None** | Already compatible |
| `frontend/public/js/graph.js` | **None** | Already compatible |
| `frontend/public/js/api.js` | **None** | No changes |

### 7.2 index.html

Add router.js to script load order, **before** app.js:

```html
<script src="js/api.js"></script>
<script src="js/graph.js"></script>
<script src="js/concept-map.js"></script>
<script src="js/search.js"></script>
<script src="js/router.js"></script>   <!-- NEW -->
<script src="js/app.js"></script>
```

### 7.3 app.js — Function Signatures

Add `skipRoute` parameter (default `false`) to three functions. When `skipRoute` is true, the function performs its work but does not call `router.push()`. This prevents double-pushing when the popstate handler restores state.

**selectWord:**
```javascript
async function selectWord(word, lang, skipRoute = false) {
    // ... existing logic unchanged ...
    if (!skipRoute) {
        router.push({ view: "etymology", word, lang });
    }
}
```

**switchView:**
```javascript
function switchView(view, skipRoute = false) {
    if (view === activeView) return;
    // ... existing logic unchanged ...
    if (!skipRoute) {
        router.push({ view });
    }
}
```

**loadConceptMap:**
```javascript
async function loadConceptMap(concept, pos, skipRoute = false) {
    // ... existing logic unchanged ...
    if (!skipRoute) {
        router.push({ view: "concept", concept, pos });
    }
}
```

### 7.4 app.js — updateDOMFromState() Helper

New function that syncs all DOM controls and globals to match a parsed state object. Called on popstate and on initial load.

```javascript
function updateDOMFromState(state) {
    // Connection type checkboxes
    const typeSet = new Set((state.types || "inh,bor,der").split(","));
    document.querySelectorAll("#ety-filters input[type=checkbox]").forEach((cb) => {
        cb.checked = typeSet.has(cb.value);
    });

    // Layout dropdown + global
    document.getElementById("layout-select").value = state.layout || "era-layered";
    currentLayout = state.layout || "era-layered";

    // Similarity slider + display + global
    const sim = state.similarity != null ? state.similarity : 100;
    document.getElementById("similarity-slider").value = sim;
    document.getElementById("similarity-value").textContent = (sim / 100).toFixed(2);
    currentSimilarityThreshold = sim / 100;

    // POS radio buttons
    const posRadio = document.querySelector(
        `input[name="concept-pos"][value="${state.pos || ""}"]`
    );
    if (posRadio) posRadio.checked = true;

    // Etymology edges checkbox
    document.getElementById("show-etymology-edges").checked =
        state.etymEdges != null ? state.etymEdges : true;

    // Search input values
    if (state.view === "etymology" && state.word) {
        document.getElementById("search-input").value = state.word;
    }
    if (state.view === "concept" && state.concept) {
        document.getElementById("concept-search-input").value = state.concept;
    }
}
```

### 7.5 app.js — Initialization (replaces line 247)

The hardcoded `selectWord("wine", "English")` is replaced with router-driven initialization:

```javascript
// Register popstate handler for back/forward
router.onNavigate((state) => {
    activeView = "";  // reset so switchView's early-return guard doesn't skip
    updateDOMFromState(state);
    switchView(state.view, true);
    if (state.view === "etymology") {
        selectWord(state.word, state.lang, true);
    } else if (state.view === "concept") {
        loadConceptMap(state.concept, state.pos, true);
    }
});

// Initialize router (parses URL, normalizes, attaches popstate listener)
router.initialize();

// Load initial view from URL params
const initial = router.state();
updateDOMFromState(initial);
if (initial.view === "concept") {
    switchView("concept", true);
    loadConceptMap(initial.concept, initial.pos, true);
} else {
    selectWord(initial.word, initial.lang, true);
}
```

**Note on switchView guard:** `switchView()` has `if (view === activeView) return` on line 52. On initial load, `activeView` starts as `"etymology"` (line 10), so `switchView("etymology")` would be a no-op — which is fine, the DOM is already in etymology state. For concept view, `switchView("concept")` will work because `"concept" !== "etymology"`. In the popstate handler, we reset `activeView = ""` before calling switchView to ensure it always executes.

### 7.6 app.js — Filter Handlers

Each filter handler is modified to pass `skipRoute = true` to the primary function (so it doesn't pushState), then explicitly calls `router.replace()`:

| Handler | Current Code | New Code |
|---|---|---|
| Connection types (line 152) | `selectWord(currentWord, currentLang)` | `selectWord(currentWord, currentLang, true)` then `router.replace({ types: getSelectedTypes() })` |
| Layout selector (line 168) | `selectWord(currentWord, currentLang)` | `selectWord(currentWord, currentLang, true)` then `router.replace({ layout: layoutSelect.value })` |
| Similarity slider (line 225) | `updateConceptEdges()` | Add `router.replace({ similarity: parseInt(similaritySlider.value) })` after |
| Etymology edges (line 233) | `updateConceptEdges()` | Add `router.replace({ etymEdges: e.target.checked })` after |
| POS radio (line 238) | `loadConceptMap(currentConcept, getSelectedPos())` | `loadConceptMap(currentConcept, pos, true)` then `router.replace({ pos })` |

### 7.7 concept-map.js — Cross-View Navigation

The "View in Etymology Graph" button (lines 382-384) currently calls both `switchView()` and `selectWord()`, which would create two history entries. Fix by passing `skipRoute = true` to switchView:

```javascript
// Before:
switchView("etymology");
selectWord(word, lang);

// After:
switchView("etymology", true);  // switch view without pushing
selectWord(word, lang);          // single push: { view: "etymology", word, lang }
```

---

## 8. Cross-View Navigation Pattern

This pattern applies to both the existing "View in Etymology Graph" and the planned "View in Concept Graph" feature:

```javascript
// From concept → etymology (existing, in concept-map.js)
switchView("etymology", true);       // switch view without pushing
selectWord(word, lang);              // single push: { view: "etymology", word, lang }

// From etymology → concept (future)
switchView("concept", true);         // switch view without pushing
loadConceptMap(concept, pos);        // single push: { view: "concept", concept, pos }
// Future: could add highlight param via router.replace({ highlight: `${word}:${lang}` })
```

The pattern is always: `switchView(target, true)` + primary navigation function. The primary navigation function creates one history entry capturing both the view switch and the target state.

---

## 9. Adding a New View (Future)

To add e.g. a "Phonetic Map" view:

1. **router.js**: Add to `VIEW_PARAMS`:
   ```javascript
   phonetic: {
     word:    { default: "" },
     range:   { default: "all" },
     cluster: { default: "", parse: String },
   }
   ```
2. **app.js**: Add `else if (state.view === "phonetic")` branches in popstate handler and initialization
3. **No router core changes needed**

---

## 10. Edge Cases

| Edge Case | Scenario | Handling |
|---|---|---|
| Default word navigation | User searches "wine" in English | URL stays `/` — all defaults omitted from buildURL |
| Duplicate pushes | Same word searched twice | `push()` compares old vs new URL, skips if identical |
| switchView early return | popstate needs to force view change | Handler resets `activeView = ""` before calling switchView |
| Double push from cross-view | "View in Etymology" button | skipRoute on switchView, selectWord handles single push |
| Invalid word in URL | `/?word=notaword` | selectWord's existing error handling shows single-node fallback |
| localStorage vs URL for layout | URL says era-layered, localStorage says force-directed | URL takes precedence on load; localStorage still updated on manual change |
| View param isolation | Switching from concept to etymology | Concept params (concept, similarity, etc.) discarded from URL entirely |
| Unknown view in URL | `/?view=nonexistent` | Falls back to default view with default params |

---

## 11. Test Cases

### 11.1 Basic URL Functionality

- Load `/` → shows wine/English etymology graph, URL stays `/`
- Load `/?word=fire&lang=Latin` → shows fire in Latin, URL preserved
- Load `/?word=apple` → shows apple in English (lang defaults)
- Load `/?view=concept&concept=water` → shows concept map for "water"
- Load `/?view=concept&concept=fire&similarity=75` → concept map, slider at 75%

### 11.2 Browser Back/Forward

- Navigate wine → fire → apple, press back twice → URL shows `/`, graph shows wine
- Press forward → `/?word=fire`, graph shows fire
- Back/forward does NOT traverse filter adjustments (slider, types, layout changes)
- Back/forward correctly switches between etymology ↔ concept views

### 11.3 Filter State in URL

- Change types to just "inherited" → URL updates to `/?word=fire&types=inh` (replaceState)
- Press back → goes to previous word (skips filter change)
- Change layout to force-directed → URL shows `/?word=fire&layout=force-directed`
- Adjust similarity slider to 75 → URL shows `/?view=concept&concept=water&similarity=75`

### 11.4 Cross-View Navigation

- On concept map, click "View in Etymology Graph" for word "oak" → single history entry created
- Press back → returns to concept map (not an intermediate state)

### 11.5 State Consistency on Restore

- Copy URL from address bar, open in new tab → identical view renders
- All DOM controls match URL state:
  - Search input shows correct word/concept
  - Checkboxes match types param
  - Slider matches similarity param
  - POS radio matches pos param
  - Layout dropdown matches layout param
  - Correct view toggle button is active

### 11.6 Edge Cases

- Search for "wine" (default) → URL stays clean `/`
- Rapid back/forward presses → each popstate correctly restores different state
- Refresh page at any URL → current view/state fully restored
- Load `/?word=xyz123` (nonexistent word) → fallback single node shown, URL preserved

---

## 12. Implementation Priorities

### Phase 1 (Core — make it work)

1. Create `router.js` with VIEW_PARAMS registry, parseURL, buildURL, push, replace, initialize
2. Add `<script>` tag to `index.html`
3. Add `skipRoute` parameter to selectWord, switchView, loadConceptMap in `app.js`
4. Replace hardcoded startup with router initialization
5. Wire up popstate handler with `updateDOMFromState`

### Phase 2 (Filters)

6. Update all filter handlers to call `router.replace()` — types, layout, similarity, POS, etymEdges
7. Fix cross-view navigation in `concept-map.js` (skipRoute on switchView)

### Phase 3 (Verification)

8. Run through all test cases in section 11
9. ESLint pass

---

## 13. Important Notes for Implementer

**On the existing architecture:** All scripts share the global scope via `<script>` tags (no module bundler). `router.js` must expose a global `router` object. It loads before `app.js` in the script order.

**On the skipRoute pattern:** The `skipRoute = false` default parameter means all existing call sites (search.js, graph.js, concept-map.js) continue working without changes — they'll push to history by default. Only app.js's filter handlers and popstate handler need to pass `true`.

**On switchView's guard:** `switchView()` has `if (view === activeView) return` (line 52 of app.js). The popstate handler works around this by setting `activeView = ""` before calling switchView. Don't remove the guard — it's correct for normal usage.

**On localStorage:** The layout selector currently persists to localStorage (line 170 of app.js). Keep this behavior, but on page load the URL takes precedence. If URL says `layout=force-directed`, use that regardless of what localStorage says.

**On nginx:** The SPA fallback (`try_files $uri $uri/ /index.html`) is already configured in `nginx.conf`. No server-side changes needed.

**On future "View in Concept Graph" feature:** The router already supports this pattern. When implementing, follow the cross-view navigation pattern in section 8. The `highlight` param placeholder in VIEW_PARAMS can be uncommented and used to auto-select the source word's node in the concept graph after rendering.
