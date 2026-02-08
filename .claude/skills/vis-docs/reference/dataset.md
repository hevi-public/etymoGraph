# DataSet API

`vis.DataSet` is a reactive data container. Changes automatically trigger network re-renders.

## Constructor

```javascript
const ds = new vis.DataSet(items?, options?);
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `fieldId` | String | `'id'` | Field name used as unique identifier |
| `queue` | Boolean/Object | — | Batch changes. Object: `{ delay: ms, max: count }` |

## CRUD Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `add` | `(data, senderId?)` | `Id[]` | Add item(s). Throws if ID exists |
| `update` | `(data, senderId?)` | `Id[]` | Update existing or create new (shallow merge) |
| `updateOnly` | `(data, senderId?)` | `Id[]` | Deep merge. Throws if item not found |
| `remove` | `(id\|ids\|object, senderId?)` | `Id[]` | Remove by ID, array of IDs, or object with ID |
| `clear` | `(senderId?)` | `Id[]` | Remove all items |

`data` can be a single item (Object) or array of items.

### add vs update vs updateOnly

| Method | Item exists? | Item missing? | Merge type |
|--------|-------------|---------------|------------|
| `add` | **Throws** | Creates | — |
| `update` | Shallow merge | Creates | Top-level properties replaced |
| `updateOnly` | Deep merge | **Throws** | Nested objects merged recursively |

**Important for vis.js node/edge updates**: Use `update()` for batch property changes. Only include changed properties — unchanged properties are preserved.

```javascript
// Update only the color of specific nodes
nodesDS.update([
    { id: "a", color: "red" },
    { id: "b", color: { background: "blue", border: "#fff" } }
]);
```

## Query Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `get` | `(id?, options?)` | Object/Array | Get item(s) by ID or all items |
| `getIds` | `(options?)` | `Id[]` | Get all IDs (with optional filter) |
| `forEach` | `(callback, options?)` | — | Iterate items: `(item, id) => {}` |
| `map` | `(callback, options?)` | Array | Map items: `(item, id) => result` |
| `distinct` | `(field)` | Array | Unique values for a field |
| `min` | `(field)` | Object/null | Item with minimum value |
| `max` | `(field)` | Object/null | Item with maximum value |

### Query options

Available for `get`, `getIds`, `forEach`, `map`:

| Option | Type | Description |
|--------|------|-------------|
| `fields` | String[]/Object | Properties to include. Object maps to rename: `{ newName: 'oldName' }` |
| `filter` | Function | `(item) => boolean`. Include items where true |
| `order` | String/Function | Sort by field name, or `(a, b) => number` |
| `returnType` | String | `'Array'` (default) or `'Object'` (keyed by ID) |

```javascript
// Get all nodes with level > 0
const descendants = nodesDS.get({
    filter: (item) => item.level > 0,
    order: 'level'
});

// Get just IDs of hidden nodes
const hiddenIds = nodesDS.getIds({
    filter: (item) => item.hidden
});
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `length` | Number | Item count |

## Events

Subscribe: `ds.on(event, callback)`. Unsubscribe: `ds.off(event, callback)`.

| Event | Trigger |
|-------|---------|
| `'add'` | Items added, or new items created via `update()` |
| `'update'` | Existing items updated |
| `'remove'` | Items removed |
| `'*'` | Any of the above |

### Callback signature

```javascript
ds.on('update', (event, properties, senderId) => {
    // event: 'add' | 'update' | 'remove'
    // properties: { items: Id[], oldData?: Object[], data?: Object[] }
    // senderId: optional sender ID from CRUD call
});
```

| Field | Type | Present in | Description |
|-------|------|-----------|-------------|
| `properties.items` | `Id[]` | All events | Affected item IDs |
| `properties.oldData` | `Object[]` | update, remove | Previous item state |
| `properties.data` | `Object[]` | update | Changed fields only |

## Queue Batching

When `queue` is enabled, changes are buffered and applied in batch.

```javascript
const ds = new vis.DataSet([], { queue: { delay: 500, max: 100 } });

// Changes are queued...
ds.add({ id: 1, label: "A" });
ds.update({ id: 1, label: "B" });
// ...and flushed after 500ms or 100 changes, whichever comes first

ds.flush();        // Force immediate flush
ds.setOptions({ queue: false });  // Disable queuing
```

## Common Patterns in etymoGraph

```javascript
// Batch color update (brightness on node selection)
nodesDataSet.update(nodes.map(n => ({
    id: n.id,
    color: computedColor,
    font: { color: `rgba(255,255,255,${opacity})` }
})));

// Replace all edges (concept map threshold change)
edgesDS.clear();
edgesDS.add(newEdges);

// Iterate for base color storage
edgesDataSet.forEach((e) => {
    edgeBaseColors[e.id] = { color: e.color.color, highlight: e.color.highlight };
});
```
