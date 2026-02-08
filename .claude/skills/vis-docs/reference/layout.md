# Layout Configuration

Controls initial node positioning. Set via `options.layout`.

## Top-Level Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `randomSeed` | Number/String | undefined | Seed for deterministic random positioning. Same seed = same layout |
| `improvedLayout` | Boolean | true | Use Kamada-Kawai algorithm for better initial positions. Auto-clusters networks > `clusterThreshold` nodes |
| `clusterThreshold` | Number | 150 | Node count above which improved layout auto-clusters for speed |

## Hierarchical Layout

Enabled via `hierarchical: true` or `hierarchical: { enabled: true, ... }`.

**Important**: When hierarchical is enabled, vis.js auto-switches the physics solver to `hierarchicalRepulsion`. The `level` property on nodes determines vertical position.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hierarchical.enabled` | Boolean | false | Toggle hierarchical layout |
| `hierarchical.direction` | String | `'UD'` | Flow direction: `'UD'` (up-down), `'DU'`, `'LR'` (left-right), `'RL'` |
| `hierarchical.levelSeparation` | Number | 150 | Distance between levels (px) |
| `hierarchical.nodeSpacing` | Number | 100 | Min distance between nodes on free axis |
| `hierarchical.treeSpacing` | Number | 200 | Distance between disconnected trees |
| `hierarchical.blockShifting` | Boolean | true | Shift branches to reduce whitespace |
| `hierarchical.edgeMinimization` | Boolean | true | Reposition nodes to minimize edge length |
| `hierarchical.parentCentralization` | Boolean | true | Re-center parent nodes after layout |
| `hierarchical.sortMethod` | String | `'hubsize'` | `'hubsize'` (high-degree nodes at top) or `'directed'` (follow edge direction) |
| `hierarchical.shakeTowards` | String | `'leaves'` | `'roots'` (align roots) or `'leaves'` (align leaves) |

### Hierarchical Tips

- Set `node.level` manually for precise control. Nodes without `level` get auto-assigned.
- Use `sortMethod: 'directed'` when edges represent parent-child relationships.
- Pair with `physics.hierarchicalRepulsion` for best results.
- `blockShifting` and `edgeMinimization` improve appearance but take extra computation.
