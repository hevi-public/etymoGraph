# Interaction Configuration

Controls user input behavior. Set via `options.interaction`.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dragNodes` | Boolean | true | Allow dragging unfixed nodes |
| `dragView` | Boolean | true | Allow panning the canvas |
| `hideEdgesOnDrag` | Boolean | false | Hide edges while panning (performance) |
| `hideEdgesOnZoom` | Boolean | false | Hide edges while zooming (performance) |
| `hideNodesOnDrag` | Boolean | false | Hide nodes while panning (performance) |
| `hover` | Boolean | false | Enable hover colors on nodes |
| `hoverConnectedEdges` | Boolean | true | Highlight edges when hovering a node |
| `multiselect` | Boolean | false | Ctrl-click / long-press adds to selection |
| `navigationButtons` | Boolean | false | Show on-canvas navigation buttons |
| `selectable` | Boolean | true | Allow selecting nodes/edges |
| `selectConnectedEdges` | Boolean | true | Select edges when selecting a node |
| `tooltipDelay` | Number | 300 | Delay (ms) before showing `title` tooltip |
| `zoomSpeed` | Number | 1 | Zoom sensitivity multiplier |
| `zoomView` | Boolean | true | Allow scroll-wheel zoom |

## Keyboard Navigation

Enable via `keyboard: true` (uses defaults) or `keyboard: { enabled: true, ... }`.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `keyboard.enabled` | Boolean | false | Toggle keyboard shortcuts |
| `keyboard.speed.x` | Number | 1 | Horizontal pan speed per key |
| `keyboard.speed.y` | Number | 1 | Vertical pan speed per key |
| `keyboard.speed.zoom` | Number | 0.02 | Zoom speed per key |
| `keyboard.bindToWindow` | Boolean | true | Bind keys to window (works regardless of focus) |
| `keyboard.autoFocus` | Boolean | true | Auto-focus network on hover (when `bindToWindow: false`) |

## Project-specific Notes

etymoGraph disables `zoomView` and implements custom trackpad handling via a `wheel` event listener on the container:
- `ctrlKey` (pinch gesture) → zoom via `network.moveTo({ scale })`
- Otherwise → pan via `network.moveTo({ position })` adjusted by `getScale()`

This gives trackpad users natural two-finger scrolling for pan and pinch for zoom.
