# SPC-00007: Shared Graph Utility Extraction

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-02-11 |
| **Modifies** | SPC-00005 (enables G6 reuse of BFS hop-distance computation) |
| **Modified-by** | — |

## Summary

Extract `computeHopDistances` from `graph.js` into `graph-common.js` so all renderers (vis.js, G6) can compute BFS hop distances from a clicked node. This is the foundation for highlight/dim features in G6.

## Changes

### Move `computeHopDistances` to `graph-common.js`

The function at `graph.js:854-876` performs BFS from a start node, returning a map of `nodeId → hopCount`. Currently it reads vis.js DataSet with `{from, to}` fields. The shared version accepts:
- A plain array of edge objects
- Configurable field names (`fromKey`/`toKey`) defaulting to `"from"`/`"to"` — G6 uses `"source"`/`"target"`

### Update `graph.js` call site

`applyBrightnessFromNode()` converts vis.js DataSet to a plain array before calling the shared function. No behavior change.

## Files Changed

| File | Changes |
|---|---|
| `frontend/public/js/graph-common.js` | Add `computeHopDistances(edges, startId, fromKey, toKey)` |
| `frontend/public/js/graph.js` | Remove local function, update `applyBrightnessFromNode()` to use shared version |

## Tests (TDD — write first)

**Unit tests** in `frontend/tests/graph-common.test.js`:

| Test | Input | Expected |
|---|---|---|
| Returns 0 for start node | Linear A→B→C, start=A | `dist[A] === 0` |
| Returns 1 for direct neighbors | Linear A→B→C, start=A | `dist[B] === 1` |
| Correct distances in linear chain | A→B→C→D, start=A | `{A:0, B:1, C:2, D:3}` |
| Correct distances in branching tree | A→B, A→C, B→D | `{A:0, B:1, C:1, D:2}` |
| Undefined for disconnected nodes | A→B, C isolated, start=A | `dist[C] === undefined` |
| Works with source/target keys | `{source,target}` edges, start=A | Same BFS result |
| Empty edge list | No edges, start=A | `{A: 0}` |
| Bidirectional traversal | A→B, start=B | `{B:0, A:1}` (edges are undirected) |

Also test `opacityForHops`: 0→1.0, 1→0.9, 2→0.5, 3→0.1, 100→0.1.

## Verification

1. `make test-frontend` — all unit tests pass
2. Load `/?word=wine` (vis.js) — highlight behavior unchanged
