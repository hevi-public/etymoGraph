# Edge Configuration Options

All options can be set globally (in `options.edges`) or per-edge. Per-edge overrides global. Set to `null` to revert to default.

## Identity

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | String | auto UUID | Unique edge identifier |
| `from` | Number/String | **required** | Source node ID |
| `to` | Number/String | **required** | Target node ID |
| `label` | String | undefined | Text on edge (canvas-rendered, no HTML) |
| `title` | String/Element | undefined | Hover tooltip |
| `hidden` | Boolean | false | Not rendered, but still in physics |
| `physics` | Boolean | true | Participates in physics simulation |
| `value` | Number | undefined | When set, width scales via `scaling` options |

## Width & Sizing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `width` | Number | 1 | Edge thickness (px). Unused when `value` scaling active |
| `hoverWidth` | Number/Function | 0.5 | Added to width on hover. Function: `(width) => newWidth` |
| `selectionWidth` | Number/Function | 1 | Added to width when selected |
| `length` | Number | undefined | Override spring rest length in physics |

### Scaling (when `value` is set)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `scaling.min` | Number | 1 | Min scaled width |
| `scaling.max` | Number | 15 | Max scaled width |
| `scaling.label.enabled` | Boolean | false | Scale label with edge |
| `scaling.label.min` | Number | 14 | Min label font size |
| `scaling.label.max` | Number | 30 | Max label font size |
| `scaling.label.maxVisible` | Number | 30 | Max perceived size at 100% zoom |
| `scaling.label.drawThreshold` | Number | 5 | Min visible size when zoomed out |
| `scaling.customScalingFunction` | Function | — | `(min, max, total, value) => 0..1` |

## Arrows

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `arrows` | String/Object | undefined | String shorthand: `'to'`, `'from'`, `'to, from'`, `'middle'` |
| `arrows.to.enabled` | Boolean | false | Arrow at destination |
| `arrows.to.type` | String | `'arrow'` | `'arrow'`, `'bar'`, `'circle'`, `'image'` |
| `arrows.to.scaleFactor` | Number | 1 | Arrow size multiplier |
| `arrows.to.src` | String | undefined | Image URL (for `type: 'image'`) |
| `arrows.to.imageWidth` | Number | undefined | Image arrow width |
| `arrows.to.imageHeight` | Number | undefined | Image arrow height |
| `arrows.from` | Object | — | Same sub-options as `arrows.to` |
| `arrows.middle` | Object | — | Same sub-options. Negative `scaleFactor` flips direction |
| `arrowStrikethrough` | Boolean | true | Line extends through arrow. false = line ends at arrow |

### Endpoint Offset

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `endPointOffset.from` | Number | 0 | Negative = toward center, positive = outward |
| `endPointOffset.to` | Number | 0 | Same. Requires `arrowStrikethrough: true` |

## Color

**Note**: `color.inherit` defaults to `'from'` — edges inherit source node color unless explicitly set.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `color` | String/Object | Object | String sets all states at once |
| `color.color` | String | `'#848484'` | Normal state |
| `color.highlight` | String | `'#848484'` | Selected state |
| `color.hover` | String | `'#848484'` | Hover state |
| `color.inherit` | String/Boolean | `'from'` | `true`/`false`, `'from'`, `'to'`, `'both'` |
| `color.opacity` | Number | 1.0 | Applied to all color variants (0-1) |

## Dashes

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dashes` | Boolean/Array | false | `true` = default dash. Array: `[dash, gap, dash, gap, ...]` |

## Smooth Curves

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `smooth` | Boolean/Object | `{ enabled: true, type: 'dynamic' }` | `false` = straight lines |
| `smooth.enabled` | Boolean | true | Toggle curve rendering |
| `smooth.type` | String | `'dynamic'` | See types table below |
| `smooth.roundness` | Number | 0.5 | Curvature (0-1) for non-dynamic types |
| `smooth.forceDirection` | String/Boolean | false | For `cubicBezier`: `'horizontal'`, `'vertical'`, `'none'` |

### Smooth Curve Types

| Type | Description |
|------|-------------|
| `dynamic` | Bezier via physics-controlled support node. Best quality, most expensive |
| `continuous` | Smooth curve through node centers. No support node. Good default |
| `discrete` | Stepped curve through node boundaries |
| `diagonalCross` | Diagonal line to node boundary |
| `straightCross` | Horizontal/vertical to node boundary |
| `horizontal` | Horizontal control points |
| `vertical` | Vertical control points |
| `curvedCW` | Clockwise arc. Control curvature with `roundness` |
| `curvedCCW` | Counter-clockwise arc |
| `cubicBezier` | Cubic bezier. Use with `forceDirection` for hierarchical layouts |

**Performance tip**: `dynamic` creates a physics node per edge. For large networks, use `continuous` or `straightCross`.

## Font

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `font` | String/Object | Object | Shorthand: `'size face color'` |
| `font.color` | String | `'#343434'` | Text color |
| `font.size` | Number | 14 | Font size (px) |
| `font.face` | String | `'arial'` | Font family |
| `font.background` | String | undefined | Background rect behind text |
| `font.strokeWidth` | Number | 2 | Text outline (0 = off) |
| `font.strokeColor` | String | `'#ffffff'` | Outline color |
| `font.align` | String | `'horizontal'` | `'horizontal'`, `'top'`, `'middle'`, `'bottom'` |
| `font.vadjust` | Number | 0 | Vertical offset (positive = down) |
| `font.multi` | Boolean/String | false | `true`, `'html'`, `'markdown'`/`'md'` |
| `font.bold` | Object | false | `{ color, size, face, mod, vadjust }` |
| `font.ital` | Object | false | Same structure |
| `font.boldital` | Object | false | Same structure |
| `font.mono` | Object | false | Same structure (default face: courier new, size 15) |
| `labelHighlightBold` | Boolean | true | Bold label when selected |

## Self-Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `selfReference.size` | Number | 20 | Loop radius when from === to |
| `selfReference.angle` | Number | `Math.PI / 4` | Loop position (radians). Default: top-right |
| `selfReference.renderBehindTheNode` | Boolean | true | Draw full circle or clip at node |

## Shadow

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `shadow` | Boolean/Object | false | `true` enables with defaults |
| `shadow.enabled` | Boolean | false | Toggle |
| `shadow.color` | String | `'rgba(0,0,0,0.5)'` | Shadow color |
| `shadow.size` | Number | 10 | Blur radius |
| `shadow.x` | Number | 5 | X offset |
| `shadow.y` | Number | 5 | Y offset |

## Interaction

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chosen` | Boolean/Object | true | Selection/hover styling |
| `chosen.edge` | Function/Boolean | undefined | `(values, id, selected, hovering) => {}` |
| `chosen.label` | Function/Boolean | undefined | `(values, id, selected, hovering) => {}` |

## Width Constraint

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `widthConstraint` | Number/Boolean/Object | false | Max label width |
| `widthConstraint.maximum` | Number | undefined | Breaks label text at spaces |
