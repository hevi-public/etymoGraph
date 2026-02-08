# Network Events

Register via `network.on(event, callback)`. Remove via `network.off(event, callback)`.

## Interaction Events

All interaction events share a common structure unless noted.

### Common callback shape
```javascript
{
    nodes: [nodeId, ...],        // clicked/selected node IDs
    edges: [edgeId, ...],        // clicked/selected edge IDs
    event: Event,                // original DOM event
    pointer: {
        DOM: { x, y },          // position in DOM coords
        canvas: { x, y }        // position in canvas coords
    }
}
```

| Event | Trigger | Extra fields |
|-------|---------|-------------|
| `click` | Single click/tap | `items: [{ nodeId } \| { edgeId }]` — all items at click position |
| `doubleClick` | Double click | Same as click |
| `oncontext` | Right-click | Same as click |
| `hold` | Long press (click and hold) | Same as click |
| `select` | Selection changes | — |
| `selectNode` | Node selected | — |
| `selectEdge` | Edge selected | — |
| `deselectNode` | Node deselected | `previousSelection: { nodes, edges }` |
| `deselectEdge` | Edge deselected | `previousSelection: { nodes, edges }` |

### Drag Events

| Event | Trigger | Callback |
|-------|---------|----------|
| `dragStart` | Drag begins | Common shape |
| `dragging` | During drag | Common shape |
| `dragEnd` | Drag ends | Common shape |
| `controlNodeDragging` | Dragging control node (edit mode) | `{ nodes, edges, pointer, controlEdge: { from, to } }` |
| `controlNodeDragEnd` | Control node drag ends | Same as controlNodeDragging |

### Hover Events

| Event | Trigger | Callback |
|-------|---------|----------|
| `hoverNode` | Mouse enters node | `{ node: nodeId }` |
| `blurNode` | Mouse leaves node | `{ node: nodeId }` |
| `hoverEdge` | Mouse enters edge | `{ edge: edgeId }` |
| `blurEdge` | Mouse leaves edge | `{ edge: edgeId }` |

**Note**: Requires `interaction.hover: true` for hover/blur events.

### Zoom Event

| Event | Trigger | Callback |
|-------|---------|----------|
| `zoom` | Zoom changes | `{ direction: '+' \| '-', scale: Number, pointer: { x, y } }` |

## Physics Events

| Event | Trigger | Callback |
|-------|---------|----------|
| `startStabilizing` | Physics begins stabilizing | — (no parameters) |
| `stabilizationProgress` | Progress update | `{ iterations: Number, total: Number }` |
| `stabilizationIterationsDone` | All iterations done | — |
| `stabilized` | Physics reaches minVelocity | `{ iterations: Number }` |

### Stabilization flow
1. `startStabilizing` fires once
2. `stabilizationProgress` fires every `updateInterval` iterations
3. `stabilizationIterationsDone` fires when max iterations reached
4. `stabilized` fires when all nodes below `minVelocity`

## Rendering Events

| Event | Trigger | Callback |
|-------|---------|----------|
| `beforeDrawing` | Before nodes/edges render | `ctx` (CanvasRenderingContext2D) — draw behind |
| `afterDrawing` | After nodes/edges render | `ctx` (CanvasRenderingContext2D) — draw on top |

**Usage**: Draw custom backgrounds, grid lines, labels, era bands, etc.

```javascript
network.on("beforeDrawing", (ctx) => {
    ctx.fillStyle = "rgba(255,255,255,0.03)";
    ctx.fillRect(-1000, -1000, 2000, 2000);
    // coordinates are in canvas space (not DOM)
});
```

## View Events

| Event | Trigger | Callback |
|-------|---------|----------|
| `animationFinished` | `moveTo`/`fit`/`focus` animation completes | — |
| `resize` | Canvas size changes | `{ width, height, oldWidth, oldHeight }` |

## Configuration Event

| Event | Trigger | Callback |
|-------|---------|----------|
| `configChange` | Configurator option changes | Options object with changed values |
