# SPC-00008: G6 Degree-Aware Force Layout

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-02-11 |
| **Modifies** | SPC-00005 (improves G6 layout quality), SPC-00006 (builds on force parameter tuning) |
| **Modified-by** | — |

## Summary

Improve G6's force-directed layout to match vis.js's degree-aware and level-aware behavior. Currently G6 uses uniform forces for all nodes/edges, producing layouts where high-degree hubs overlap and the root drifts. This spec adds 5 layout improvements.

## Changes

All in `g6-adapter.js` `render()` function.

### 1. Degree-based edge distance

Replace fixed `link.distance: 200` with a function:
```javascript
distance: function(edge) {
    var combined = (degree[edge.source] || 1) + (degree[edge.target] || 1);
    return 110 + 50 * Math.log2(1 + combined);
}
```
Matches vis.js formula at `graph.js:574`. Busy nodes spread further apart.

### 2. Level-based charge strength

Replace fixed `charge.strength: -500` with a function:
```javascript
strength: function(node) {
    if (node.data?.isRoot) return -2000;
    var level = node.data?.level || 0;
    return -500 / Math.pow(2, Math.abs(level));
}
```
Root has strong repulsion (gravitational anchor). Distant-level nodes have weaker charge, staying peripheral. Mirrors vis.js mass formula at `graph.js:314`.

### 3. Root node pinning

Set `fx: 0, fy: 0` in root node data so d3-force pins it at origin. Fallback: `onTick` callback that resets root position each tick.

### 4. Degree-based edge opacity

Update `edge.style.stroke` to compute per-edge opacity:
```javascript
var edgeOpacity = Math.max(0.2, 1.0 / Math.log2(2 + maxDeg));
```
Matches vis.js `graph.js:552`. Edges between high-degree hubs fade; peripheral edges stay clear.

### 5. Label hiding for dense connections

Update `edge.style.labelText` to return `""` when both endpoints have degree > 5. Matches vis.js `graph.js:553`.

### Prerequisite: Degree map

Compute node degrees from edges before graph creation. Store in node data for layout function access. Style functions close over the degree map via `render()` scope.

## Files Changed

| File | Changes |
|---|---|
| `frontend/public/js/g6-adapter.js` | Degree computation, layout functions, edge styling, root pinning |

## Tests

Layout quality is visual — no automated tests. Verified via Playwright screenshots:

| Scenario | Expected |
|---|---|
| `/?word=wine&renderer=g6` | Root near center, well-spaced, labels readable |
| `/?word=water&renderer=g6` | Large graph: high-degree edges dimmer, no label clutter |
| Compare with `/?word=wine&renderer=vis` | Similar spacing feel, not identical |

## Verification

1. Load `/?word=wine&renderer=g6` — root anchored near center
2. High-degree nodes spread further from neighbors than low-degree
3. Edge opacity varies: busy edges dimmer, peripheral edges brighter
4. Labels hidden on edges between nodes with degree > 5
5. vis.js renderer unchanged
