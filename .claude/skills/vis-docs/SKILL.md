---
name: vis-docs
description: vis.js Network & DataSet API reference for etymology graph development
---

# vis.js Network Documentation

Quick reference for vis.js v4.x (vis-network standalone UMD bundle).

## Architecture

```javascript
// Constructor
const network = new vis.Network(container, { nodes, edges }, options);

// Data uses reactive DataSet — updates auto-render
const nodes = new vis.DataSet([...]);
const edges = new vis.DataSet([...]);
nodes.update([{ id: "foo", color: "red" }]); // triggers re-render
```

**Options modules**: nodes, edges, layout, interaction, physics, manipulation, groups, configure
**CDN**: `unpkg.com/vis-network/standalone/umd/vis-network.min.js`

## Project Usage

**graph.js** (etymology graph):
- Solver: `forceAtlas2Based` with custom gravitational/spring params
- 2 layout strategies: `force-directed` (root pinned at 0,0 with mass decay) and `era-layered` (fixed Y by era tier, family clustering on X)
- `beforeDrawing` canvas event for era band rendering
- Reactive DataSet updates for brightness/opacity changes on node selection
- `moveTo` with animation for click-to-center and zoom controls
- `getPositions`, `getScale`, `getViewPosition` for trackpad pan/zoom
- Wheel event handler: ctrlKey for pinch-zoom, else pan

**concept-map.js** (phonetic similarity):
- Solver: `barnesHut` with custom params
- `DataSet.clear()` + `DataSet.add()` for edge threshold updates
- Same trackpad/zoom pattern as graph.js

## Quick Reference

### Create network
```javascript
const network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, options);
```

### Create DataSet
```javascript
const ds = new vis.DataSet(itemsArray);
```

### Batch update nodes
```javascript
nodesDataSet.update([{ id: "a", color: "red" }, { id: "b", color: "blue" }]);
```

### Navigate viewport
```javascript
network.moveTo({
    position: { x: 0, y: 0 },
    scale: 1.5,
    animation: { duration: 400, easingFunction: "easeInOutQuad" }
});
```

### Fit all nodes
```javascript
network.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } });
```

### Click event
```javascript
network.on("click", (params) => {
    // params: { nodes: [], edges: [], pointer: { DOM: {x,y}, canvas: {x,y} }, event }
});
```

### Get node positions
```javascript
const pos = network.getPositions([nodeId])[nodeId]; // { x, y }
```

### Custom canvas drawing
```javascript
network.on("beforeDrawing", (ctx) => {
    // ctx is CanvasRenderingContext2D — draw behind nodes/edges
});
network.on("afterDrawing", (ctx) => {
    // draw on top of nodes/edges
});
```

## Reference Index

| Topic | File | Key contents |
|-------|------|-------------|
| Node options | `reference/nodes.md` | Shape, color, font, physics, size, constraints |
| Edge options | `reference/edges.md` | Arrows, smooth curves, color, dashes, width |
| Physics | `reference/physics.md` | All 4 solvers with params, stabilization, tuning |
| Layout | `reference/layout.md` | Random seed, hierarchical, improved layout |
| Interaction | `reference/interaction.md` | Drag, zoom, hover, keyboard, tooltips |
| Methods | `reference/methods.md` | All Network instance methods with signatures |
| Events | `reference/events.md` | All events with callback parameter shapes |
| DataSet | `reference/dataset.md` | CRUD, queries, events, queue batching |

## Shape Types (16)

`ellipse`, `circle`, `database`, `box`, `text`, `image`, `circularImage`, `diamond`, `dot`, `star`, `triangle`, `triangleDown`, `hexagon`, `square`, `icon`, `custom`

**With label inside**: box, circle, ellipse, database, text
**With label below**: image, circularImage, diamond, dot, star, triangle, triangleDown, hexagon, square, icon

## Easing Functions (13)

`linear`, `easeInQuad`, `easeOutQuad`, `easeInOutQuad`, `easeInCubic`, `easeOutCubic`, `easeInOutCubic`, `easeInQuart`, `easeOutQuart`, `easeInOutQuart`, `easeInQuint`, `easeOutQuint`, `easeInOutQuint`

## Smooth Curve Types (10)

| Type | Description |
|------|-------------|
| `dynamic` | Default. Bezier via physics-controlled support node |
| `continuous` | Smooth curve through node centers (no support node) |
| `discrete` | Stepped curve through node boundaries |
| `diagonalCross` | Diagonal line to node boundary |
| `straightCross` | Horizontal/vertical to node boundary |
| `horizontal` | Horizontal control points |
| `vertical` | Vertical control points |
| `curvedCW` | Clockwise arc (use roundness to control) |
| `curvedCCW` | Counter-clockwise arc |
| `cubicBezier` | Cubic bezier (use with forceDirection) |
