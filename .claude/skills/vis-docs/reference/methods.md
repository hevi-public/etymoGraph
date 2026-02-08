# Network Methods

All methods called on a `vis.Network` instance: `network.methodName(...)`.

## Global

| Method | Signature | Description |
|--------|-----------|-------------|
| `destroy` | `()` | Remove network, clean up DOM and listeners |
| `setData` | `({ nodes, edges })` | Replace all data. Accepts DataSet or Array |
| `setOptions` | `(options)` | Update configuration. Triggers re-render |
| `on` | `(event, callback)` | Register event listener |
| `off` | `(event, callback)` | Remove event listener |
| `once` | `(event, callback)` | Single-fire event listener |

## Canvas

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `canvasToDOM` | `({ x, y })` | `{ x, y }` | Convert canvas coords to DOM coords |
| `DOMtoCanvas` | `({ x, y })` | `{ x, y }` | Convert DOM coords to canvas coords |
| `redraw` | `()` | — | Force redraw |
| `setSize` | `(width, height)` | — | Set canvas dimensions (strings, e.g. `'800px'`) |

## Selection

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `getSelection` | `()` | `{ nodes: [], edges: [] }` | Get current selection |
| `getSelectedNodes` | `()` | `Id[]` | Selected node IDs |
| `getSelectedEdges` | `()` | `Id[]` | Selected edge IDs |
| `getNodeAt` | `({ x, y })` | `Id \| undefined` | Node at DOM position |
| `getEdgeAt` | `({ x, y })` | `Id \| undefined` | Edge at DOM position |
| `selectNodes` | `(nodeIds, highlightEdges?)` | — | Select nodes. `highlightEdges` default true |
| `selectEdges` | `(edgeIds)` | — | Select edges |
| `setSelection` | `({ nodes, edges }, options?)` | — | Set selection. Options: `{ unselectAll, highlightEdges }` |
| `unselectAll` | `()` | — | Clear all selections |

## Viewport

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `getScale` | `()` | `Number` | Current zoom level |
| `getViewPosition` | `()` | `{ x, y }` | Canvas center point |
| `fit` | `(options?)` | — | Zoom to fit. See options below |
| `focus` | `(nodeId, options?)` | — | Center and optionally zoom to node |
| `moveTo` | `(options)` | — | Move/zoom/animate viewport. See options below |
| `releaseNode` | `()` | — | Release focused node |

### fit options
```javascript
network.fit({
    nodes: [id1, id2],        // optional: fit only these nodes
    minZoomLevel: 0.1,        // optional: minimum zoom
    maxZoomLevel: 5,          // optional: maximum zoom
    animation: {              // optional: true, false, or object
        duration: 1000,
        easingFunction: 'easeInOutQuad'
    }
});
```

### focus options
```javascript
network.focus(nodeId, {
    scale: 2.0,               // optional: zoom level
    offset: { x: 0, y: 0 },  // optional: offset from center
    locked: true,             // optional: keep focused on node
    animation: {              // optional
        duration: 1000,
        easingFunction: 'easeInOutQuad'
    }
});
```

### moveTo options
```javascript
network.moveTo({
    position: { x: 0, y: 0 }, // optional: canvas coords to center on
    scale: 1.0,                // optional: zoom level
    offset: { x: 0, y: 0 },   // optional: pixel offset from center
    animation: {               // optional: false for instant, or:
        duration: 1000,        // ms
        easingFunction: 'easeInOutQuad'
    }
});
```

### Easing functions (13)
`linear`, `easeInQuad`, `easeOutQuad`, `easeInOutQuad`, `easeInCubic`, `easeOutCubic`, `easeInOutCubic`, `easeInQuart`, `easeOutQuart`, `easeInOutQuart`, `easeInQuint`, `easeOutQuint`, `easeInOutQuint`

## Information

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `getPositions` | `(nodeIds?)` | `{ id: { x, y } }` | Node positions in canvas coords. No args = all nodes |
| `getPosition` | `(nodeId)` | `{ x, y }` | Single node position |
| `storePositions` | `()` | — | Write current positions back to DataSet (x, y fields) |
| `moveNode` | `(nodeId, x, y)` | — | Move node to canvas position |
| `getBoundingBox` | `(nodeId)` | `{ top, left, right, bottom }` | Node bounding box in canvas coords |
| `getConnectedNodes` | `(nodeOrEdgeId, direction?)` | `Id[]` | Adjacent nodes. Direction: `'from'`, `'to'`, undefined (both) |
| `getConnectedEdges` | `(nodeId)` | `Id[]` | All edges attached to node |

## Clustering

| Method | Signature | Description |
|--------|-----------|-------------|
| `cluster` | `(options)` | Cluster nodes by `joinCondition(nodeOptions)`. Options: `{ joinCondition, processProperties, clusterNodeProperties, clusterEdgeProperties }` |
| `clusterByConnection` | `(nodeId, options?)` | Cluster a node with all its neighbors |
| `clusterByHubsize` | `(hubsize?, options?)` | Cluster nodes with degree >= hubsize |
| `clusterOutliers` | `(options?)` | Cluster nodes with only 1 connection |
| `findNode` | `(nodeId)` | Returns path from cluster to base node: `[clusterId, ..., nodeId]` |
| `isCluster` | `(nodeId)` | `Boolean`. Check if node is a cluster |
| `getNodesInCluster` | `(clusterId)` | `Id[]`. Direct children of cluster |
| `openCluster` | `(clusterId, options?)` | Release cluster contents. Options: `{ releaseFunction }` |
| `getClusteredEdges` | `(baseEdgeId)` | Edge IDs created from clustering |
| `getBaseEdges` | `(clusteredEdgeId)` | Original edge IDs before clustering |
| `updateEdge` | `(edgeId, options)` | Update edge across cluster layers |
| `updateClusteredNode` | `(nodeId, options)` | Update cluster node properties |

## Physics

| Method | Signature | Description |
|--------|-----------|-------------|
| `startSimulation` | `()` | Resume physics |
| `stopSimulation` | `()` | Pause physics. Fires `stabilized` event |
| `stabilize` | `(iterations?)` | Run N iterations of stabilization. Default: from options |

## Layout

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `getSeed` | `()` | Number | Get the random seed used for layout |
