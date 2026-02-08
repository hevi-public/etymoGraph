# Node Configuration Options

All options can be set globally (in `options.nodes`) or per-node (in node data). Per-node overrides global. Set to `null` to revert to default.

## Identity & Position

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | Number/String | — | **Required.** Unique node identifier |
| `label` | String | undefined | Text displayed in/under node (depends on shape) |
| `x` | Number | undefined | Initial X position (canvas coords) |
| `y` | Number | undefined | Initial Y position (canvas coords) |
| `level` | Number | undefined | Hierarchy level (for hierarchical layout) |
| `group` | String | undefined | Group ID; inherits group styling |
| `hidden` | Boolean | false | Not rendered, but still in physics simulation |
| `title` | String/Element | undefined | Hover tooltip (HTML or plain text) |
| `value` | Number | undefined | When set, nodes scale via `scaling` options |

## Shape & Size

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `shape` | String | `'ellipse'` | See shape types below |
| `size` | Number | 25 | Size for shapes without internal labels |
| `margin` | Number/Object | 5 | Label margin. Object: `{ top, right, bottom, left }` |
| `widthConstraint` | Number/Boolean/Object | false | Min/max width. Object: `{ minimum, maximum }` |
| `heightConstraint` | Number/Boolean/Object | false | Min height. Object: `{ minimum, valign: 'top'|'middle'|'bottom' }` |

**Shape types (16):**
- Label inside: `box`, `circle`, `ellipse`, `database`, `text`
- Label below: `image`, `circularImage`, `diamond`, `dot`, `star`, `triangle`, `triangleDown`, `hexagon`, `square`, `icon`
- Custom: `custom` (uses `ctxRenderer`)

### Scaling (when `value` is set)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `scaling.min` | Number | 10 | Min node size |
| `scaling.max` | Number | 30 | Max node size |
| `scaling.label.enabled` | Boolean | false | Scale label with node |
| `scaling.label.min` | Number | 14 | Min label font size |
| `scaling.label.max` | Number | 30 | Max label font size |
| `scaling.label.maxVisible` | Number | 30 | Max perceived size at 100% zoom |
| `scaling.label.drawThreshold` | Number | 5 | Min visible size when zoomed out |
| `scaling.customScalingFunction` | Function | — | `(min, max, total, value) => 0..1` |

## Color

**Important**: vis.js has 3 color states (default, highlight, hover). If you set `color` as a string, only the default state is set. To style all states, use the object form.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `color` | String/Object | Object | String sets background only |
| `color.background` | String | `'#97C2FC'` | Background color |
| `color.border` | String | `'#2B7CE9'` | Border color |
| `color.highlight.background` | String | `'#D2E5FF'` | Selected background |
| `color.highlight.border` | String | `'#2B7CE9'` | Selected border |
| `color.hover.background` | String | `'#D2E5FF'` | Hover background |
| `color.hover.border` | String | `'#2B7CE9'` | Hover border |
| `opacity` | Number | undefined | Overall node opacity (0-1) |

## Border

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `borderWidth` | Number | 1 | Border width (normal) |
| `borderWidthSelected` | Number | 2 | Border width (selected) |
| `shapeProperties.borderDashes` | Array/Boolean | false | Dash pattern `[dash, gap]`. `true` = `[5, 15]` |
| `shapeProperties.borderRadius` | Number | 6 | Corner radius for `box` shape |

## Font

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `font` | String/Object | Object | Shorthand: `'size face color'` |
| `font.color` | String | `'#343434'` | Text color |
| `font.size` | Number | 14 | Font size (px) |
| `font.face` | String | `'arial'` | Font family |
| `font.background` | String | undefined | Background rect behind text |
| `font.strokeWidth` | Number | 0 | Text outline width (0 = off) |
| `font.strokeColor` | String | `'#ffffff'` | Text outline color |
| `font.align` | String | `'center'` | `'center'` or `'left'` |
| `font.vadjust` | Number | 0 | Vertical offset (positive = down) |
| `font.multi` | Boolean/String | false | `true`, `'html'`, or `'markdown'` for multi-font |
| `font.bold` | Object | false | `{ color, size, face, mod, vadjust }` |
| `font.ital` | Object | false | Same structure as bold |
| `font.boldital` | Object | false | Same structure |
| `font.mono` | Object | false | Same structure (default face: courier new) |
| `labelHighlightBold` | Boolean | true | Bold label when selected |

### Multi-font markup

When `font.multi: true` or `'html'`:
- `<b>bold</b>`, `<i>italic</i>`, `<code>mono</code>`, `<b><i>boldital</i></b>`

When `font.multi: 'markdown'` or `'md'`:
- `*bold*`, `_italic_`, `` `mono` ``, `*_boldital_*`

Newlines: `\n` in label text creates line breaks.

## Physics

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mass` | Number | 1 | Repulsion mass. Values < 1 not recommended |
| `physics` | Boolean | true | Participates in physics simulation |
| `fixed` | Boolean/Object | false | Prevents movement |
| `fixed.x` | Boolean | false | Lock X axis |
| `fixed.y` | Boolean | false | Lock Y axis |

## Image & Icon

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `image` | String/Object | undefined | URL for `image`/`circularImage` shapes |
| `image.unselected` | String | undefined | Normal state image |
| `image.selected` | String | undefined | Selected state image |
| `brokenImage` | String | undefined | Fallback image URL |
| `imagePadding` | Number/Object | 0 | Padding. Object: `{ top, right, bottom, left }` |
| `shapeProperties.interpolation` | Boolean | true | Resample images when scaled |
| `shapeProperties.useImageSize` | Boolean | false | Use actual image dimensions |
| `shapeProperties.useBorderWithImage` | Boolean | false | Apply color/border to image shapes |
| `shapeProperties.coordinateOrigin` | String | `'center'` | `'center'` or `'top-left'` |

### Icon (shape: `'icon'`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `icon.face` | String | `'FontAwesome'` | Icon font family |
| `icon.code` | String | undefined | Unicode char (e.g. `'\uf007'`) |
| `icon.size` | Number | 50 | Icon size (px) |
| `icon.color` | String | `'#2B7CE9'` | Icon color |
| `icon.weight` | Number/String | undefined | Font weight |

## Shadow

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `shadow` | Boolean/Object | false | `true` enables with defaults |
| `shadow.enabled` | Boolean | false | Toggle shadow |
| `shadow.color` | String | `'rgba(0,0,0,0.5)'` | Shadow color |
| `shadow.size` | Number | 10 | Blur radius |
| `shadow.x` | Number | 5 | X offset |
| `shadow.y` | Number | 5 | Y offset |

## Interaction

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chosen` | Boolean/Object | true | Enable selection/hover style changes |
| `chosen.node` | Function/Boolean | undefined | `(values, id, selected, hovering) => {}` |
| `chosen.label` | Function/Boolean | undefined | `(values, id, selected, hovering) => {}` |

## Custom Rendering

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ctxRenderer` | Function | undefined | For `shape: 'custom'`. Receives `{ ctx, id, x, y, state, style, label }` |
