# SPC-00010: G6 Concept Map Highlight

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-02-11 |
| **Modifies** | SPC-00005 (adds highlight dimming to G6 concept map) |
| **Modified-by** | — |

## Summary

Add connected-node highlighting to the G6 concept map renderer. When a user clicks a node, directly connected nodes stay bright and all others dim — matching vis.js behavior (`concept-map.js:418-461`).

Unlike the etymology graph (hop-based, SPC-00009), the concept map uses **binary** highlighting: connected or not.

## Approach

One G6 state: `inactive`.

| Element | Connected | Not connected |
|---|---|---|
| Node | Default (opacity 1.0) | `inactive` (opacity 0.2) |
| Edge | Default (opacity 1.0) | `inactive` (opacity 0.15) |

These values match vis.js concept map: `rgba(100,100,120,0.2)` for nodes, `applyRgbaOpacity(base, 0.15)` for edges.

## Changes

### State definitions

```javascript
node: { state: { inactive: { opacity: 0.2 } } }
edge: { state: { inactive: { opacity: 0.15 } } }
```

### Click handler

On `node:click`: find all edges touching the clicked node, collect connected node IDs. Set `inactive` on everything else. Single `graph.setElementState(batchMap)` call.

### Canvas click: reset

Clear all states on `canvas:click`.

### Edge update clearing

Call `_clearAllStates()` at the start of `_setEdges()` — when phonetic edges update (slider change), any existing highlight is stale.

### Explicit edge IDs in `render()`

Add `id` to etymology edges in the initial render (phonetic edges in `_setEdges` already have explicit IDs).

### Window exposure

Add `window.__g6ConceptGraph = graph` for E2E testing.

## Files Changed

| File | Changes |
|---|---|
| `frontend/public/js/g6-concept-adapter.js` | State defs, click handler, canvas reset, edge IDs, clear on edge update, window exposure |

## Tests (TDD — write first)

**E2E tests** in `tests/e2e/g6-highlight.spec.js` (same file as SPC-00009):

| Test | Scenario |
|---|---|
| Click dims unconnected | Load concept+fire+G6, click node, verify connected=`[]`, unconnected=`["inactive"]` |
| Canvas resets concept | After highlighting, click canvas, all states `[]` |
| Slider clears highlight | Highlight node, adjust similarity, all states cleared |

**E2E helpers** in `tests/e2e/helpers.js`:
- `waitForG6ConceptMap(page)` — wait for `window.__g6ConceptGraph`

## Verification

1. `/?view=concept&concept=fire&renderer=g6` — click node, connected nodes bright, others dim
2. Click canvas — all restored
3. Adjust slider — highlight cleared, new edges drawn
4. `make test-e2e` — concept highlight tests pass
5. vis.js concept map unchanged
