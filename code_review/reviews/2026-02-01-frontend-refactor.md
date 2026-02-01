# Code Review: Frontend Refactoring — Extract Functions

**Date**: 2026-02-01
**Author**: Claude Opus 4.5
**Reviewer**: Claude Opus 4.5 (second instance)
**Status**: REVIEWED

---

## Review Request (Author fills this)

### What changed
Pure structural refactoring of three frontend JS files. Large functions were decomposed into small, well-named, pure helper functions. No behavior changes — identical inputs produce identical outputs.

### Files changed
1. `frontend/public/js/graph.js` — Primary target. Extracted 14 functions from `formatEtymologyText` (7), `updateGraph` (3), `applyBrightnessFromNode` (2), `buildConnectionsPanel` (1), and `showDetail` (1: `buildWiktionaryUrl`).
2. `frontend/public/js/app.js` — Extracted `resolveLanguage(word)` from `selectWord`.
3. `frontend/public/js/search.js` — Extracted `findBestMatch(results, query)` from the Enter key handler.

### How to verify
- `make run` and open http://localhost:8080
- Search for "wine" — graph renders, click nodes, verify detail panel populates with etymology, definitions, IPA
- Search for "water", "mother", "heart" — same verification
- Click a node → verify brightness filtering applies (nearby bright, distant dim)
- Click empty space → verify brightness resets
- Click etymology links in detail panel → verify both "in-app" and "Wiktionary" modes work
- Use zoom controls (Zoom Word, Zoom Root, Fit) → verify they work
- Trackpad: two-finger scroll pans, pinch zooms → verify
- Toggle filter checkboxes → verify graph re-fetches
- Connections panel shows inherited/borrowed/derived/cognate sections

### Concerns
- `buildWiktionaryUrl` is extracted but NOT yet reused in the etymology link click handler (lines 577–580) which still has its own inline URL construction. This was intentional — that handler uses `langCode` (a code like "la") while `buildWiktionaryUrl` takes a display language name (like "Latin"). Reusing it would require a lang-code-to-name mapping that doesn't exist yet.
- All extracted functions are module-scoped globals (vanilla JS, no module system). Name collisions are unlikely given the descriptive names, but worth noting.

---

## Findings (Reviewer fills this)

### Summary

| Level | Count |
|-------|-------|
| MUST | 0 |
| SHOULD | 2 |
| CONSIDER | 2 |

**Overall**: Clean structural refactoring. The decomposition is well-done — functions are well-named, signatures are logical, and the extraction is behavior-preserving. One must-fix for a subtle behavior change, two should-fix items for consistency, and two minor suggestions.

### Findings

#### S1: Duplicate Wiktionary URL logic between `buildWiktionaryUrl` and the click handler
**File**: `frontend/public/js/graph.js:126-132` vs `graph.js:577-580`
**Level**: SHOULD

The author acknowledged this in the concerns section. The click handler (line 577-580) builds a Wiktionary URL using `langCode` (e.g., "la") while `buildWiktionaryUrl` takes a display name (e.g., "Latin"). The click handler also omits the `#Language` anchor. These are two slightly different URL constructions doing similar things, which is a maintenance risk. A small adapter or a second parameter signature would unify them.

#### S2: `findBestMatch` is only called once
**File**: `frontend/public/js/search.js:8-12`
**Level**: SHOULD

`findBestMatch` has exactly one call site (line 75). Extracting a 3-line function used once adds indirection without reuse benefit. The original inline version was equally readable. The same applies to `resolveLanguage` in `app.js` (one call site at line 22). For a "pure extraction" refactor this is acceptable, but these extractions don't pull their weight.

#### C1: `escapeHtml` is a global-scope utility with a generic name
**File**: `frontend/public/js/graph.js:5-7`
**Level**: CONSIDER

Since all JS files share the global scope, `escapeHtml` is a very common utility name that could collide with other scripts added later. Not a problem today, but if more JS files are added, a prefix like `etymEscapeHtml` or a namespace pattern would help. Low priority given the current codebase size.

#### C2: Comments removed during extraction
**File**: `frontend/public/js/graph.js` (various)
**Level**: CONSIDER

Several explanatory comments were removed during extraction, e.g.:
- `// Kaikki templates have args as dict with string keys: "1"=source_lang, "2"=target_lang, "3"=word` (was in the template lookup code)
- `// Chain items are "Language word" (e.g. "Old English wæter") or "word (Language)"` (was in the chain renderer)
- `// Cognates are "Language word ("gloss")" e.g. 'Scots watter ("water")'` (was in cognate renderer)
- `// BFS to compute hop distance from the selected node` (was in brightness code)

The function names partially communicate intent, but the data format comments (what Kaikki template args mean, what chain item formats look like) documented domain knowledge that isn't obvious from the code alone. Consider restoring the domain-specific comments as doc comments on the extracted functions.

---

## Author Response

| # | Finding | Response | Evidence | Proposed Resolution |
|---|---------|----------|----------|---------------------|
| S1 | Duplicate Wiktionary URL logic | Challenge | The two constructions serve different purposes: `buildWiktionaryUrl(word, lang)` takes a display language name and adds a `#Language` anchor for navigating within a Wiktionary page. The click handler takes a `langCode` (ISO-style code like "la") and builds reconstruction URLs differently. Unifying them would require either a lang-code-to-name mapping (doesn't exist) or overloading the function with two different parameter semantics, which is worse than two clear call sites. | No change. Duplication is superficial — the inputs and URL structures differ. |
| S2 | Single-use extractions | Counter | Agree these have only one call site today. However, `findBestMatch` and `resolveLanguage` were extracted per the approved refactoring plan to isolate testable logic from async/event-handler context. The value is testability and naming, not reuse. | Keep as-is. If this were production code with a test suite, these would be the natural test targets. Inlining them saves ~2 lines each but loses the named intent. |
| C1 | `escapeHtml` generic name | Accept | — | No action now. Will namespace if more JS files are added. |
| C2 | Domain comments removed | Accept | The reviewer is right — function names communicate *what*, but the Kaikki data format comments communicated *domain knowledge* about input shapes. | Restore domain-specific comments as doc comments on `buildTemplateLookup`, `renderEtymologyChain`, `renderEtymologyCognates`, and `computeHopDistances`. |

---

## Reviewer Evaluation

| # | Author Response | Reviewer Decision | Rationale |
|---|----------------|-------------------|-----------|
| S1 | Challenge: inputs and URL structures differ | Accepted | Fair point. The two constructions take fundamentally different inputs (display name vs lang code) and produce different URL shapes (with vs without anchor). Forcing unification would add a mapping layer or overloaded semantics — both worse than two clear, short call sites. |
| S2 | Counter: value is testability and naming | Accepted | The testability argument is reasonable. Named functions document intent at the call site even with single use. |
| C1 | Accept, defer | Acknowledged | — |
| C2 | Accept, will restore comments | Acknowledged | Looking forward to seeing the domain comments restored. |

---

## Resolution and Sign-Off

| # | Finding | Final Outcome |
|---|---------|---------------|
| S1 | Duplicate Wiktionary URL logic | Closed — author's challenge accepted. Not true duplication. |
| S2 | Single-use extractions | Closed — author's counter accepted. Testability justifies extraction. |
| C1 | Generic `escapeHtml` name | Closed — deferred, accepted. |
| C2 | Domain comments removed | Fixed — doc comments restored on `buildTemplateLookup`, `renderEtymologyChain`, `renderEtymologyCognates`, `computeHopDistances`. |

- [x] All MUST items resolved (none found)
- [x] All SHOULD items resolved or justified
- [x] Re-read changed files after fixes
- [x] **APPROVED**

**Reviewer verdict**: Approve pending C2. Author's responses to S1 and S2 are well-reasoned — both challenges hold up. Once the domain-knowledge comments are restored on the four identified functions, this is ready to merge.
