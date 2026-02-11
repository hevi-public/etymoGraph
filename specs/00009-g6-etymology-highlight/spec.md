# SPC-00009: G6 Etymology Graph Highlight/Dim

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-02-11 |
| **Modifies** | SPC-00005 (adds Phase 2 hop-based opacity feature to G6 renderer) |
| **Modified-by** | — |
| **Depends on** | SPC-00007 (shared `computeHopDistances`) |

## Summary

Add hop-distance-based highlight/dim to the G6 etymology graph renderer. When a user clicks a node, nearby nodes stay bright and distant nodes fade — matching vis.js behavior (`graph.js:854-953`).

## Approach: G6 State System

G6 v5's state system defines named states with style overrides. Setting `opacity` affects the entire node group (shape + label), which is simpler than vis.js's manual rgba manipulation per color channel.

| State | Opacity | Applied to |
|---|---|---|
| (default) | 1.0 | Clicked node (0 hops) |
| `highlight` | 0.9 | 1-hop neighbors |
| `dim` | 0.5 | 2-hop nodes |
| `faded` | 0.1 | 3+ hops / unreachable |

Edges use the same states, with opacity based on `min(fromHops, toHops)`.

## Changes

### State definitions in Graph config

Add `state` blocks to `node` and `edge` config:
```javascript
node: { style: {...}, state: { highlight: {opacity:0.9}, dim: {opacity:0.5}, faded: {opacity:0.1} } }
edge: { style: {...}, state: { highlight: {opacity:0.9}, dim: {opacity:0.5}, faded: {opacity:0.1} } }
```

### Click handler: apply highlight

On `node:click`:
1. Call `computeHopDistances(graph.getEdgeData(), nodeId, "source", "target")`
2. Build a batch state map: `{ nodeId: [], neighbor: ["highlight"], distant: ["faded"], ... }`
3. Same for edges: min-hop of endpoints determines state
4. Call `graph.setElementState(batchMap)` — single render pass

### Canvas click: reset

On `canvas:click`: set all element states to `[]` (clears all states, restores default opacity).

### Explicit edge IDs

Add `id` field to edge data mapping (G6 auto-IDs may not work with `setElementState`):
```javascript
id: e.from + "-" + (e.label || "edge") + "-" + e.to + "-" + idx
```

### selectNode() update

`selectNode(nodeId)` should also apply highlight states (not just `focusElement`).

### Window exposure for testing

Add `window.__g6Graph = graph` after `graph.render()` for E2E test access.

## Files Changed

| File | Changes |
|---|---|
| `frontend/public/js/g6-adapter.js` | State defs, click handler with BFS, canvas reset, edge IDs, window exposure |

## Tests (TDD — write first)

**E2E tests** in `tests/e2e/g6-highlight.spec.js`:

| Test | Scenario |
|---|---|
| Click node dims by hop distance | Load wine+G6, click node, verify hop-based states via `getElementState()` |
| Click canvas resets states | After highlighting, click canvas, verify all states are `[]` |
| Click different node re-highlights | Highlight node A, click node B, verify states recalculated from B |

**E2E helpers** added to `tests/e2e/helpers.js`:
- `waitForG6Graph(page)` — wait for `window.__g6Graph` with rendered nodes
- `getG6ElementStates(page, ids)` — batch-check element states

## Verification

1. `/?word=wine&renderer=g6` — click a node, see hop-based fade
2. Clicked node: full brightness. Direct neighbors: slightly dimmed. Far nodes: nearly invisible.
3. Click canvas: everything returns to full opacity
4. `make test-e2e` — G6 highlight tests pass
5. vis.js highlight unchanged
