# Physics Configuration

Controls node/edge simulation. Set via `options.physics`.

## Global Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | Boolean | true | Toggle physics on/off |
| `solver` | String | `'barnesHut'` | `'barnesHut'`, `'forceAtlas2Based'`, `'repulsion'`, `'hierarchicalRepulsion'` |
| `maxVelocity` | Number | 50 | Cap node velocity to help stabilization |
| `minVelocity` | Number | 0.1 | Stop threshold. Network freezes when all nodes below this |
| `timestep` | Number | 0.5 | Simulation step size. Larger = faster but less stable |
| `adaptiveTimestep` | Boolean | true | Auto-adjust timestep during stabilization |

## barnesHut (default)

General-purpose solver. Uses quadratic repulsion (force ~ 1/distance^2). Good for most graphs.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `theta` | Number | 0.5 | Barnes-Hut approximation. Lower = more accurate, slower |
| `gravitationalConstant` | Number | -2000 | Repulsion strength. More negative = stronger repulsion |
| `centralGravity` | Number | 0.3 | Pull toward center |
| `springLength` | Number | 95 | Edge rest length |
| `springConstant` | Number | 0.04 | Spring stiffness. Higher = stronger pull |
| `damping` | Number | 0.09 | Velocity damping (0-1). Higher = faster settling |
| `avoidOverlap` | Number | 0 | Node overlap prevention (0-1) |

## forceAtlas2Based

Better for large networks. Uses linear repulsion (force ~ 1/distance). Nodes spread more evenly.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `theta` | Number | 0.5 | Barnes-Hut approximation threshold |
| `gravitationalConstant` | Number | -50 | Repulsion (linear falloff). More negative = stronger |
| `centralGravity` | Number | 0.01 | Pull toward center (distance-independent) |
| `springLength` | Number | 100 | Edge rest length |
| `springConstant` | Number | 0.08 | Spring stiffness |
| `damping` | Number | 0.4 | Velocity damping (0-1) |
| `avoidOverlap` | Number | 0 | Overlap prevention (0-1) |

## repulsion

Simple solver. Good for small, sparse layouts.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `nodeDistance` | Number | 100 | Repulsion range of influence |
| `centralGravity` | Number | 0.2 | Pull toward center |
| `springLength` | Number | 200 | Edge rest length |
| `springConstant` | Number | 0.05 | Spring stiffness |
| `damping` | Number | 0.09 | Velocity damping (0-1) |

## hierarchicalRepulsion

For use with hierarchical layout. Nodes repel only on the "free" axis.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `nodeDistance` | Number | 120 | Repulsion range |
| `centralGravity` | Number | 0.0 | Pull toward center |
| `springLength` | Number | 100 | Edge rest length |
| `springConstant` | Number | 0.01 | Spring stiffness |
| `damping` | Number | 0.09 | Velocity damping (0-1) |
| `avoidOverlap` | Number | 0 | Overlap prevention (0-1) |

## Stabilization

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `stabilization.enabled` | Boolean | true | Run stabilization on load |
| `stabilization.iterations` | Number | 1000 | Max iterations |
| `stabilization.updateInterval` | Number | 50 | Iterations between progress events |
| `stabilization.onlyDynamicEdges` | Boolean | false | Freeze nodes, only stabilize dynamic edge curves |
| `stabilization.fit` | Boolean | true | Zoom to fit after stabilization |

## Wind

Constant force applied to all nodes each simulation step.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `wind.x` | Number | 0 | Horizontal force (positive = right) |
| `wind.y` | Number | 0 | Vertical force (positive = down) |

## Tuning Guide

### Solver Selection

| Use case | Solver | Why |
|----------|--------|-----|
| General graphs (<500 nodes) | `barnesHut` | Good balance of quality and speed |
| Large graphs (500+ nodes) | `forceAtlas2Based` | Linear repulsion spreads nodes more evenly |
| Small sparse graphs | `repulsion` | Simplest, fastest |
| Tree/hierarchy | `hierarchicalRepulsion` | Pairs with hierarchical layout |

### Key Parameter Effects

| Want to... | Adjust | Direction |
|------------|--------|-----------|
| Spread nodes farther apart | `gravitationalConstant` | More negative |
| Compact the graph | `centralGravity` | Increase |
| Longer edges | `springLength` | Increase |
| Stiffer/shorter edges | `springConstant` | Increase |
| Faster settling | `damping` | Increase (toward 1) |
| Prevent node overlap | `avoidOverlap` | Increase (toward 1) |
| Stop jittering | `minVelocity` | Increase slightly |
| Disable physics after layout | call `network.stopSimulation()` after `stabilized` event |

### Project-specific notes

etymoGraph uses `forceAtlas2Based` with `stabilization: false` (continuous animation). The root node is pinned at (0,0) with mass 5, while other nodes have exponentially decaying mass by level. The era-layered layout uses fixed Y positions with very high damping (0.95) and weak springs to allow gentle X-axis settling.
