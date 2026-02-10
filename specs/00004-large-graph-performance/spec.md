# SPC-00004: Large-Graph Performance — Adaptive Rendering & Physics

| Field | Value |
|---|---|
| **Status** | implemented |
| **Created** | 2026-02-10 |
| **Modifies** | — |
| **Modified-by** | Reverted concept-map.js changes (smooth, minVelocity, improvedLayout, physics freeze) — these optimizations were scoped to graph.js per constraint 12 but were incorrectly also applied to concept-map.js, causing edges to become invisible |

---

**Context:** Etymology Explorer uses vis-network to render etymology graphs. On graphs with 3000+ nodes, the UI is janky when zoomed out (all nodes visible) but smooth when zoomed in (~10 nodes visible). This zoom-dependent slowdown suggests canvas rendering is the dominant cost, since vis.js does viewport culling (fewer visible nodes = less draw work) but simulates physics on all nodes regardless of viewport. A diagnostic module (`perf-diag.js`) has been added to confirm this hypothesis before implementation.

---

## 1. Purpose

Make large etymology graphs (3000+ nodes) interactive at 60fps regardless of zoom level by:

1. Reducing per-frame canvas rendering cost when many nodes are visible
2. Reducing physics simulation cost after the layout has stabilized
3. Preserving the current look and behavior for small graphs (<200 nodes)

---

## 2. Diagnostic Step

A diagnostic module already exists at `frontend/public/js/perf-diag.js`. It is wired into the network via two globals set in `graph.js` (line ~981): `window.__etymoNetwork` and `window.__etymoNodesDS`.

Before implementing any fix, run the diagnostic to confirm the bottleneck:

1. Start the app, load a word with a large graph, zoom out to see all nodes
2. Open DevTools console, run `perfDiag.benchmark()`
3. Read the output — it prints per-frame rendering cost, physics cost, and names the dominant bottleneck

**If rendering is the bottleneck:** implement sections 4, 5, 6, 7 (the expected path).
**If physics is the bottleneck:** implement sections 8, 9, 10.
**Regardless:** implement section 11 (cleanup) after verification.

---

## 3. Architecture Overview

```
                         updateGraph(data)
                               │
                               ▼
                    ┌──────────────────────┐
                    │  baseGraphOptions()   │─── R1: edge smooth toggle
                    │  line ~662            │─── R4: improvedLayout toggle
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  new vis.Network()    │─── R5: stabilized listener
                    │  line ~979            │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  wheel handler        │─── R2: LOD threshold check
                    │  line ~1012           │─── R3: cluster/decluster
                    └──────────────────────┘
```

All changes are scoped to `frontend/public/js/graph.js`. Key locations:

- `baseGraphOptions(overrides)` (line ~662) — builds vis.js options, deep-merges layout overrides
- `updateGraph(data)` (line ~933) — creates the vis.Network instance. Node count is `data.nodes.length`
- `graphContainer.addEventListener("wheel", ...)` (line ~1012) — custom zoom/pan handler
- `LAYOUTS` object (line ~709) — layout strategy registry (`force-directed`, `era-layers`)
- `LANGUAGE_FAMILIES` (line ~196) — maps family names to hex colors

Current relevant config:

- Edges: `smooth: { type: "continuous" }` (bezier curves)
- Physics: `solver: "forceAtlas2Based"`, `stabilization: false`
- Interaction: `zoomView: false` (zoom handled by wheel listener)

---

## 4. R1: Straight Edges on Large Graphs

**Problem:** Bezier path calculation + stroke is the single most expensive per-edge rendering operation in vis.js. Each curved edge requires computing a bezier control point and stroking a path. Straight lines are a single `lineTo` call.

**Behavior:**

- When `data.nodes.length > 200`, edges use `smooth: false` (straight lines)
- When `data.nodes.length <= 200`, edges use `smooth: { type: "continuous" }` (current behavior)

**Implementation:** In `updateGraph()`, before the `new vis.Network()` call. The node count is known at that point. Either modify the options object returned by `layout.getGraphOptions()`, or pass the count into `baseGraphOptions()` and branch there.

Do not change `baseGraphOptions()` signature if avoidable — prefer modifying the options object after it's returned, since the threshold is a graph-level concern not a layout concern.

---

## 5. R2: Level-of-Detail by Zoom Scale

**Problem:** At low zoom levels, all nodes and edges are visible with full labels and fonts. The label rendering (text measurement, multi-line layout, stroke) adds significant per-node cost that provides no value when nodes are too small to read.

**Behavior:**

- When `network.getScale() < LOD_THRESHOLD` (start with 0.4):
  - Edge label font color set to `"transparent"`
  - Node font color set to `"transparent"` for non-selected nodes
- When `network.getScale() >= LOD_THRESHOLD`:
  - Restore original font colors

**Implementation:** Hook into the existing `wheel` event handler on `graphContainer` (line ~1012). This is the only place zoom changes happen (since `zoomView: false` disables vis.js's built-in zoom).

Guard with a boolean flag (`lodActive`) so `network.setOptions()` is called only on threshold crossings, not on every wheel event. Calling `setOptions` on every tick would thrash the renderer.

```
wheel event
  → compute new scale
  → if crossed LOD_THRESHOLD boundary:
       → setOptions({ nodes: { font: ... }, edges: { font: ... } })
       → flip lodActive flag
```

**Do NOT** use `beforeDrawing` for this — it fires every frame and calling `setOptions` from within it causes infinite redraw loops.

**Threshold tuning:** 0.4 is a starting point. The right value is where node labels become unreadable anyway. Test with a large graph and adjust.

---

## 6. R3: Zoom-Based Clustering

**Problem:** Even with straight edges and hidden labels, drawing 3000 individual box-shaped nodes is expensive. Clustering reduces the node count to ~20-50 aggregate nodes when zoomed out.

**Behavior:**

- Only activates when the graph has 500+ nodes (don't cluster small graphs)
- When `network.getScale() < CLUSTER_THRESHOLD` (start with 0.25):
  - Cluster nodes by language family using `network.cluster()`
  - Each cluster node uses:
    - Label: `"{family} ({count})"`
    - Shape: `"dot"`
    - Size: `Math.sqrt(count) * 5`
    - Color: family color from `LANGUAGE_FAMILIES`
  - Store active cluster IDs in a module-level array
- When `network.getScale() > DECLUSTER_THRESHOLD` (0.35, hysteresis gap):
  - Call `network.openCluster(id)` for each stored cluster ID
  - Clear the stored IDs array

**Hysteresis:** The 0.10 gap between cluster (0.25) and decluster (0.35) thresholds prevents rapid cluster/decluster cycling when the user zooms around the boundary.

**Implementation:** Wire into the same wheel handler as R2. The clustering logic should check both `lodActive` state and node count before acting.

**Language family iteration:** Use `LANGUAGE_FAMILIES` (line ~196) as the clustering key. For each family with 2+ nodes in the current graph, create one cluster. Nodes not matching any known family get clustered into a single "Other" group.

```javascript
// Pseudocode for clustering
const familyCounts = {};
nodesDataSet.forEach(n => {
    const family = /* look up from node data */;
    familyCounts[family] = (familyCounts[family] || 0) + 1;
});

for (const [family, count] of Object.entries(familyCounts)) {
    if (count < 2) continue;
    const clusterId = `cluster:${family}`;
    network.cluster({
        joinCondition: (nodeOptions) => /* node belongs to family */,
        clusterNodeProperties: {
            id: clusterId,
            label: `${family} (${count})`,
            shape: "dot",
            size: Math.sqrt(count) * 5,
            color: LANGUAGE_FAMILIES[family] || "#A0A0B8",
        },
    });
    activeClusters.push(clusterId);
}
```

**Node-to-family mapping:** The node's language family is not stored directly on vis nodes. Options for resolving it:

1. **Preferred:** When building vis nodes in the layout's `buildVisNodes()`, store the family as a custom property (e.g., `node.family`). This is accessible in the `joinCondition` callback.
2. **Alternative:** Maintain a separate `nodeIdToFamily` map alongside `nodeBaseColors`, populated during `updateGraph()`.

---

## 7. R4: Disable improvedLayout for Large Graphs

**Problem:** vis.js's `improvedLayout` runs a Kamada-Kawai preprocessing pass on initial layout. For large graphs this is O(n²) and wasted when `computeTreePositions()` already provides initial coordinates.

**Behavior:** When `data.nodes.length > 200`, set `layout.improvedLayout: false` in the options object.

**Implementation:** Same location as R1 — after `layout.getGraphOptions()` returns, override the value before passing to the Network constructor.

---

## 8. R5: Freeze Physics After Stabilization

**Problem:** If physics is the bottleneck, the simulation continues computing forces on all nodes every tick even after the layout has visually settled.

**Behavior:**

- Listen for the `stabilized` event on the network
- On stabilization, call `network.setOptions({ physics: { enabled: false } })`
- On `dragStart`, re-enable physics so the dragged node interacts with neighbors
- On `dragEnd`, set a 500ms timeout, then disable physics again

**Implementation:** Add event listeners in `updateGraph()` after the Network constructor.

```javascript
network.on("stabilized", () => {
    network.setOptions({ physics: { enabled: false } });
});
network.on("dragStart", () => {
    network.setOptions({ physics: { enabled: true } });
});
network.on("dragEnd", () => {
    setTimeout(() => {
        network.setOptions({ physics: { enabled: false } });
    }, 500);
});
```

---

## 9. R6: Tune Physics Convergence

**Problem:** Default vis.js physics parameters may cause the simulation to run longer than necessary before reaching equilibrium.

**Behavior:** Set `minVelocity: 2.0` and `maxVelocity: 50` in the etymology graph physics configuration. These make the simulation settle faster by raising the velocity floor at which vis.js considers the simulation "stable".

**Implementation:** Add to the physics config in `baseGraphOptions()` or in the layout-specific `getGraphOptions()` overrides.

---

## 10. R7: Solver Fallback for Very Large Graphs

**Problem:** `forceAtlas2Based` is efficient for medium graphs but may underperform `barnesHut` at very high node counts (1000+). Barnes-Hut with high `theta` aggressively approximates distant node interactions.

**Behavior:** When `data.nodes.length > 1000`, override the solver:

- Solver: `"barnesHut"`
- `barnesHut.theta`: `0.8`
- Keep other physics parameters (damping, spring constants) from the current layout config

**Implementation:** In `updateGraph()`, same location as R1 and R4 — modify the options object before the Network constructor call.

---

## 11. R8: Remove Diagnostic Scaffolding

After the fix is verified with `perfDiag.benchmark()`, remove all temporary diagnostic code:

1. Delete `frontend/public/js/perf-diag.js`
2. Remove its `<script>` tag from `index.html` (line ~107)
3. Remove the two `window.__etymo*` assignment lines from `graph.js` (line ~981-982) and their comment

---

## 12. Constraints

- **Small graph preservation:** Graphs with <200 nodes must look and behave identically to current behavior. No visual regressions — curved edges, full labels, current physics behavior all preserved.
- **File scope:** All changes in `graph.js`. Do not modify `concept-map.js`, `app.js`, `search.js`, `router.js`, or the backend. The only exceptions are `index.html` (for script tag cleanup in R8) and `perf-diag.js` (deletion in R8).
- **No new dependencies.** vis-network's built-in APIs (`setOptions`, `cluster`, `openCluster`, events) are sufficient.
- **LAYOUTS abstraction:** If a requirement needs layout-specific behavior, add it to the layout object rather than hardcoding layout name checks in `updateGraph`. For graph-level concerns (node count thresholds), modify the options object after `layout.getGraphOptions()` returns.
- **Concept map isolation:** `concept-map.js` has its own vis.Network instance. If it develops similar performance issues, it gets its own spec. Don't cross-wire the two.

---

## 13. Edge Cases

| Edge Case | Scenario | Handling |
|---|---|---|
| Graph grows past threshold | User loads small graph, then loads large one | `updateGraph()` runs fresh each time — threshold check happens on each call |
| Zoom during physics | User zooms while physics is still running | LOD and clustering logic read current scale, work regardless of physics state |
| Cluster click | User clicks a cluster node | vis.js fires click event with cluster ID. The existing click handler (`network.on("click", ...)`) should guard against cluster IDs not being in `currentNodes` |
| Rapid zoom through both thresholds | User pinch-zooms quickly from zoomed-in to fully zoomed-out | LOD triggers at 0.4, clustering at 0.25 — both fire from the same wheel handler, both guarded by flags |
| Decluster then re-cluster | User zooms in past 0.35 (decluster) then back out past 0.25 (cluster) | Hysteresis gap prevents flicker. Clustering rebuilds from scratch each time (no stale state) |
| Network destroy and recreate | User searches for a new word | `updateGraph()` calls `network.destroy()` first. All event listeners and clusters are cleaned up. LOD flag and cluster array should be reset at top of `updateGraph()` |
| Zero-node family | A language family has only 1 node | Skip clustering for families with <2 nodes (they'd just become a cluster of 1) |
| Physics already frozen | R5 fires stabilized, then user doesn't drag | No-op — physics stays disabled, rendering continues at low cost |

---

## 14. Test Cases

### 14.1 Rendering Performance (R1–R4)

- Load a 3000+ node graph, zoom to fit all → frame rate ≥ 60fps (draw time < 16ms per `perfDiag.benchmark()`)
- Same graph, zoom in to ~10 nodes → behavior identical to current (curved edges, visible labels)
- Load a <200 node graph → curved edges, labels visible at all zoom levels, `improvedLayout` active
- Zoom out on large graph → labels disappear below scale 0.4
- Zoom back in past 0.4 → labels reappear
- Zoom out past 0.25 on 500+ node graph → nodes cluster by language family
- Zoom in past 0.35 → clusters open, individual nodes visible
- Rapid zoom in/out around 0.25–0.35 → no flicker, no errors

### 14.2 Physics Performance (R5–R7)

- Load a large graph, wait for it to settle → physics auto-disables (check via `perfDiag.report()` showing `Physics: false`)
- Drag a node → node responds, neighbors react (physics re-enabled)
- Release node → after ~500ms, physics disables again
- Load a 1000+ node graph → solver is barnesHut (check via DevTools or options inspection)
- Load a <1000 node graph → solver remains forceAtlas2Based

### 14.3 Interaction Integrity

- Click a node on a large graph (zoomed out, LOD active) → detail panel still opens correctly
- Click a cluster node → no crash, detail panel does not open (or shows cluster info)
- Search for a word while clustered → `updateGraph()` resets everything, new graph renders clean
- Browser back/forward (SPC-00003) still works correctly with large graphs
- Zoom controls (focus word, focus root, fit all) work correctly at all LOD states

### 14.4 Cleanup (R8)

- `perf-diag.js` deleted, no `<script>` tag in `index.html`
- No `window.__etymo*` globals in `graph.js`
- Console `perfDiag` is undefined (no leftover global)

---

## 15. Implementation Priorities

### Phase 1 — Diagnose

1. Run `perfDiag.benchmark()` on a large graph
2. Confirm which bottleneck dominates — proceed with the matching requirement set

### Phase 2 — Core fix

3. Implement R1 (straight edges) — highest impact-to-effort ratio
4. Implement R4 (disable improvedLayout) — trivial, immediate benefit on load time
5. Implement R2 (LOD labels) — moderate impact, straightforward
6. If physics bottleneck: implement R5 (freeze after stabilization) + R6 (tune convergence)

### Phase 3 — Clustering

7. Implement R3 (zoom-based clustering) — highest impact but most complex
8. If physics bottleneck: implement R7 (solver fallback)

### Phase 4 — Verify & Clean

9. Run `perfDiag.benchmark()` again, confirm <16ms frame times zoomed out
10. Run through all test cases in section 14
11. Implement R8 (remove diagnostic scaffolding)

---

## 16. Important Notes for Implementer

**On the node count thresholds:** The 200-node threshold for R1 and R4 is a starting point. If the diagnostic shows rendering is still expensive at 200 nodes with straight edges, lower it. If 200-node graphs look bad with straight edges, raise it. The threshold should be tuned empirically.

**On clustering and the click handler:** The existing `network.on("click", ...)` handler (line ~988) looks up `params.nodes[0]` in `currentNodes`. Cluster node IDs (e.g., `"cluster:Germanic"`) won't match. Guard against this: `if (params.nodes.length > 0 && !network.isCluster(params.nodes[0]))`.

**On the wheel handler complexity:** R2 and R3 both add logic to the wheel handler. Keep them organized — extract a `handleZoomLOD(scale)` function rather than inlining everything in the wheel callback.

**On the `LAYOUTS` abstraction:** R1, R4, and R7 modify the options object after `layout.getGraphOptions()` returns. This preserves the layout abstraction — layouts don't need to know about performance thresholds. If a layout ever needs to opt out of a performance optimization, it can set a flag that `updateGraph()` checks.

**On existing architecture:** All scripts share global scope via `<script>` tags (no bundler). Module-level variables in `graph.js` (like `network`, `nodesDataSet`, `currentLayout`) are accessible from any code in the same file but not from other scripts unless explicitly exposed on `window`.
