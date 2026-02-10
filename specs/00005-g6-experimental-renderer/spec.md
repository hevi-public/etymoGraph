# SPC-00005: G6 v5 Experimental Renderer

| Field | Value |
|---|---|
| **Status** | approved |
| **Created** | 2026-02-10 |
| **Modifies** | SPC-00004 (adds renderer abstraction layer around performance optimizations) |
| **Modified-by** | — |

## Summary

Add G6 v5 by AntV as an experimental graph renderer alongside the existing vis.js renderer. Users switch between renderers via a dropdown in the filters panel. vis.js remains the default and is not modified. A renderer abstraction layer enables future library additions with minimal code changes.

## Motivation

The current vis.js Canvas 2D renderer hits its performance ceiling around 3,000 nodes despite SPC-00004 optimizations. With much larger graphs (10K-50K+ nodes) planned for the near future, the project needs a WebGL-capable renderer. After evaluating 8 candidate libraries (see `decision-log.md`), G6 v5 was selected for its feature parity (8-9/10), 211-contributor ecosystem, Rust-accelerated layouts, and built-in clustering/LOD/WebGL. Cytoscape.js is the documented fallback.

## Architecture

### Renderer Abstraction Layer

```
app.js → graph-renderer.js (factory) → vis-adapter.js | g6-adapter.js
                                              ↓               ↓
                                          graph.js         G6 library
                                              ↓
                                      graph-common.js (shared constants)
```

### Adapter Interface

Every renderer adapter must implement:

```javascript
{
    type: string,                        // "vis" or "g6"
    render(data): Promise<void>,         // Render graph data { nodes, edges }
    destroy(): void,                     // Clean up renderer resources
    selectNode(nodeId): void,            // Select and animate to a node
    getAvailableLayouts(): string[],     // Layout keys this renderer supports
}
```

### New Files

| File | Purpose |
|------|---------|
| `frontend/public/js/graph-common.js` | Shared constants: LANG_FAMILIES, classifyLang, EDGE_LABELS, color utilities, layout computation |
| `frontend/public/js/graph-renderer.js` | Factory: `createRenderer(type, container, callbacks)` returns adapter |
| `frontend/public/js/vis-adapter.js` | Wraps existing graph.js `updateGraph()` behind adapter interface |
| `frontend/public/js/g6-adapter.js` | G6 v5 implementation with dynamic script loading |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/public/js/graph.js` | Extract shared constants to graph-common.js; keep vis.js-specific code |
| `frontend/public/js/app.js` | Use renderer factory instead of direct `updateGraph()` call |
| `frontend/public/js/router.js` | Add `renderer: { "default": "vis" }` to etymology VIEW_PARAMS |
| `frontend/public/index.html` | Add new script tags, renderer dropdown in filters |
| `frontend/public/css/style.css` | Renderer select styles (follows layout-select pattern) |

## G6 Feature Mapping

10 vis.js features mapped to G6 v5 equivalents, implemented across phases:

| # | vis.js Feature | G6 v5 Equivalent | Phase |
|---|---------------|-------------------|-------|
| 1 | Physics (forceAtlas2Based/barnesHut) | `layout: { type: "d3-force" }` + `{ type: "forceAtlas2" }` | 1 |
| 2 | Reactive data (vis.DataSet) | `graph.setData()` / `graph.updateData()` | 1 |
| 3 | Node styling (20 colors, box, dashed borders, opacity) | `node.style: { fill, stroke, lineDash, opacity }`, type: `"rect"` | 1 |
| 4 | Edge styling (6 types, arrows, dashed, degree opacity) | `edge.style: { stroke, lineDash, endArrow }` | 1 |
| 5 | Interactions (click, drag, zoom, pan, animate) | Built-in behaviors + `graph.focusItem()` | 1 |
| 6 | Era-layered layout + canvas bands | Custom G6 layout + custom canvas layer | 2 |
| 7 | LOD (label hiding at low zoom) | G6 LOD plugin or zoom-based style update | 2 |
| 8 | Root node glow | Halo style or custom shape with shadowBlur | 2 |
| 9 | Hop-based opacity on selection | `graph.setItemState()` + state styles | 2 |
| 10 | Clustering (zoom-based, by family) | G6 combos or custom cluster plugin | 3 |

## Implementation Phases

### Phase 1: Basic G6 Rendering (this spec)

Delivers a working G6 renderer with force-directed layout and basic styling:

1. Extract shared constants to `graph-common.js`
2. Create renderer abstraction (`graph-renderer.js`)
3. Wrap existing graph.js in `vis-adapter.js`
4. Implement `g6-adapter.js` with force-directed layout + basic styling
5. Add renderer dropdown in filters popover
6. Add `renderer` param to `router.js` VIEW_PARAMS
7. Wire `app.js` to use renderer factory

**Phase 1 limitations:**
- G6 only supports force-directed layout (era-layered is vis.js only)
- No hop-based opacity on node selection
- No clustering
- Detail panel connections section empty (reads from vis.js DataSet)

### Phase 2: Feature Parity (future spec)

8. Era-layered custom layout + canvas era bands
9. LOD (hide labels below zoom threshold)
10. Root node glow styling
11. Hop-based opacity on node selection
12. Auto-switch to WebGL renderer for 1000+ nodes

### Phase 3: Clustering (future spec)

13. Zoom-based dynamic clustering by language family
14. Cluster click to expand

### Phase 4: Concept Map (future spec)

15. Apply G6 adapter to concept-map.js

## UI: Renderer Toggle

Location: Inside `#ety-filters` popover, below the layout select.

```html
<div class="filter-group-label">Renderer</div>
<select id="renderer-select" title="Graph renderer">
    <option value="vis">vis.js (stable)</option>
    <option value="g6">G6 v5 (experimental)</option>
</select>
```

Placed in filters rather than header to avoid cluttering the top bar. Follows the same pattern as `#layout-select`.

When the renderer changes:
- Current renderer is destroyed
- New renderer is created in the same container (`#graph`)
- Graph re-renders with current word data
- Layout select updates to show only available layouts
- URL updates via router (`?renderer=g6`)

## G6 Script Loading

G6 is loaded dynamically only when the user first selects it (lazy loading). This avoids the ~400KB download for users who don't use the experimental renderer.

```javascript
// g6-adapter.js
function loadG6Script() {
    if (window.G6) return Promise.resolve();
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://unpkg.com/@antv/g6@5/dist/g6.min.js";
        script.onload = resolve;
        script.onerror = () => reject(new Error("Failed to load G6"));
        document.head.appendChild(script);
    });
}
```

**CDN fallback:** If the G6 CDN is unavailable, the adapter catches the error and falls back to vis.js with a console warning.

## Router Integration

Add `renderer` parameter to etymology VIEW_PARAMS:

```javascript
etymology: {
    word:     { "default": "wine" },
    lang:     { "default": "English" },
    types:    { "default": "inh,bor,der" },
    layout:   { "default": "era-layered" },
    renderer: { "default": "vis" },
},
```

This enables shareable links with renderer selection: `/?word=water&renderer=g6`

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| G6 bundle size (+400KB gzipped) | Slower initial load | Lazy-load only when user selects G6 |
| Era-layered layout complexity in G6 | Missing feature | Phase 2; disable layout option for G6 in Phase 1 |
| Clustering gap in Phase 1-2 | Can't handle very large graphs in G6 | Document limitation; vis.js remains default |
| G6 CDN unavailable | Renderer won't load | Auto-fallback to vis.js with console warning |
| G6 v5 API instability | Breaking changes | Pin CDN to specific version |

## Cytoscape.js Fallback

If G6 proves inadequate, create `cytoscape-adapter.js` following the same adapter interface. The renderer factory makes this a drop-in replacement. Cytoscape.js has 1.5M+ weekly npm downloads, 11-year history, 246+ contributors — lowest risk of all options.

## Verification

1. **Smoke test:** Load `/?word=wine&renderer=g6` — graph renders with G6, nodes colored by family, edges show arrows, click opens detail panel
2. **Renderer switching:** Select G6 in dropdown, verify graph re-renders; switch back to vis.js, verify it works
3. **URL persistence:** Set `?renderer=g6`, refresh page — G6 loads
4. **Layout restriction:** G6 only shows force-directed in layout dropdown
5. **Performance:** Load "water" (large graph), compare vis.js vs G6
6. **No regressions:** All existing Vitest + Playwright tests pass (vis.js path unchanged)
7. **CDN failure:** Block G6 CDN URL, verify graceful fallback to vis.js

## References

- [G6 v5 Documentation](https://g6.antv.antgroup.com/)
- [G6 GitHub](https://github.com/antvis/G6)
- `specs/00005-g6-experimental-renderer/decision-log.md` — Full research and decision record
- SPC-00004 — Large graph performance optimizations (modified by this spec)
