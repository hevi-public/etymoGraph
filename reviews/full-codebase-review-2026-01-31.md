# Full Codebase Review

| Field    | Value                  |
|----------|------------------------|
| Date     | 2026-01-31             |
| Reviewer | Claude Opus 4.5        |
| Scope    | Full codebase          |
| Status   | Complete               |

## Summary

The codebase is clean, well-organized, and impressively lean for its feature set. The architecture choices (vanilla JS, FastAPI, MongoDB) are appropriate and well-executed. Most issues are SHOULD/CONSIDER level — there are a few MUST-level bugs worth fixing.

| Level    | Count |
|----------|-------|
| MUST     | 4     |
| SHOULD   | 8     |
| CONSIDER | 5     |

---

## MUST — Bugs & Correctness

### M1. `graph.js:545-549` — In-app etymology link lookup is broken for words containing `:`

The node ID format is `word:lang`, but the code splits on `:` and only takes the first part. Words with colons (or proto-language reconstructions like `*wīną`) will fail to match.

```js
const nodeId = currentNodes.find(n => {
    const [w] = n.id.split(":");
    return w === word;
});
const fullLang = nodeId ? nodeId.language : undefined;
```

The variable is named `nodeId` but it's actually a node object (the result of `.find()`). This is a naming lie — the code works accidentally because `.language` is accessed on the found node, but `nodeId` is not an ID. More critically, splitting on `:` breaks if the word itself contains a colon. Consider using `n.label === word` or splitting only on the last `:`.

### M2. `etymology.py:87-92` — Empty `types` parameter silently defaults to `inh`

```python
requested_types = set(types.split(","))
# ...
if not allowed_types:
    allowed_types = {"inh"}
```

If a user passes `types=cog` (cognates only, no ancestry types), `allowed_types` becomes empty and silently falls back to `inh`. This means requesting cognates-only still builds an `inh` ancestry tree. The frontend always sends at least one ancestry type so this doesn't surface, but the API contract is misleading.

### M3. `etymology.py:11-13` — Module-level mutable cache is not thread-safe

```python
_lang_code_to_name = {}
_lang_name_to_code = {}
```

These module-level dicts are populated on first request via `_ensure_lang_cache()`. With uvicorn's async event loop this is fine for single-worker, but under multiple workers the cache populates independently per worker (wasted work, not a correctness bug). However, the `if _lang_code_to_name:` guard has a race condition if two coroutines call `_ensure_lang_cache()` concurrently on first request — both will populate the dict simultaneously. In practice this is benign (both write the same data), but it's worth noting.

### M4. `graph.js:273-274` — Edge label overwrite loses the raw type

```js
label: EDGE_LABELS[e.label] || e.label,
```

Edges are mapped from `"inh"` to `"inherited"` when building the DataSet. Later, `buildConnectionsPanel` (`graph.js:356`) reverse-maps display labels back to raw types:

```js
const rawType = Object.keys(EDGE_LABELS).find((k) => EDGE_LABELS[k] === e.label) || e.label;
```

This round-trip works but is fragile. If a display label were ever changed or duplicated, the reverse lookup would break. Storing the raw type as a separate field on the edge would be more robust.

---

## SHOULD — Maintainability & Robustness

### S1. `graph.js:284-300` — Wheel event listener is re-added on every `updateGraph()` call

Every call to `updateGraph()` adds a new `wheel` event listener to `graphContainer` without removing the previous one. After N searches, there are N active wheel listeners, all fighting over zoom/pan. This is a memory leak and will cause increasingly erratic zoom behavior over time.

**Fix:** Remove the previous listener before adding a new one, or add it once outside `updateGraph()`.

### S2. `etymology.py:150-185` — `_expand_cognates` queries every node on every round

```python
for nid, node in list(nodes.items()):
    doc = await col.find_one(...)
```

On each cognate round, this queries MongoDB for **every** node in the graph, not just the new ones. For a graph with 100 nodes and 2 rounds, that's 200+ queries where most results are already processed. Only iterating over newly added nodes per round would be more efficient.

### S3. `words.py:8` — `get_word` returns first matching document only

```python
doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0})
```

Many words have multiple entries (different POS: noun, verb, adjective). This returns only the first one found. The API gives no indication that other entries exist.

### S4. `main.py:9` — CORS allows all origins

```python
allow_origins=["*"]
```

Fine for local development, but worth noting as something to lock down if this ever gets deployed.

### S5. `load.py:42-43` — JSON parse errors are silently swallowed

```python
except json.JSONDecodeError:
    continue
```

Malformed lines are skipped with no logging. Adding a counter for skipped lines would help diagnose data quality issues.

### S6. `requirements.txt` — No pinned versions

```
fastapi
uvicorn[standard]
motor
pydantic-settings
```

Any `pip install` could pull breaking changes. Pin major versions at minimum.

### S7. `database.py:4-5` — Global MongoDB client created at import time

```python
client = AsyncIOMotorClient(settings.mongo_uri)
db = client.etymology
```

The client is created when the module is first imported, not when the app starts. This works because Motor is lazy (doesn't actually connect until first operation), but it means the connection string is evaluated at import time and can't be overridden by test fixtures or startup events. A `get_db()` function with lazy init would be more testable.

### S8. `search.js:16` — `innerHTML` for suggestion rendering (XSS)

```js
li.innerHTML = `${item.word} <span class="lang-hint">${item.lang}</span>`;
```

`item.word` and `item.lang` come from the API (ultimately from user-submitted Wiktionary data). This is an XSS vector — if a word in the database contains HTML, it will be rendered. Use `textContent` for the word and create the span via DOM APIs instead.

---

## CONSIDER — Style & Minor Improvements

### C1. `graph.js` is 554 lines doing 4 different things

`formatEtymologyText`, graph rendering, detail panel management, and zoom controls are all in one file. This is the largest file in the frontend and could benefit from splitting — though for a vanilla JS project with no build step, the current approach is pragmatic.

### C2. `app.js:17` — Swallowed exception in `selectWord`

```js
} catch (_) {
    lang = "English";
}
```

Silent fallback to "English" when search fails. A `console.warn` would help debugging.

### C3. `nginx.conf` — No caching headers for static assets

Static JS/CSS files are served without cache headers. Adding `Cache-Control` or `expires` for `/css/` and `/js/` would improve reload performance.

### C4. `docker-compose.yml:26-27` — MongoDB port exposed to host

```yaml
ports:
  - "27017:27017"
```

Convenient for debugging, but exposes an unauthenticated MongoDB to the network. Fine for local dev; just don't deploy this as-is.

### C5. `index.html:7` — vis-network loaded from unpkg CDN without integrity hash

```html
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
```

No `integrity` or version pin. A compromised CDN or a breaking update could affect the app. Consider pinning a version and adding a subresource integrity hash.

---

## Positive Observations

- **Etymology tree algorithm** (`etymology.py`) is well-thought-out — the "first ancestry template = direct parent" filtering is the right approach for Kaikki data.
- **Search two-pass strategy** is clever — exact matches first, then prefix, properly deduplicated.
- **`re.escape(q)`** correctly used in search regex — no injection.
- **Trackpad handling** is correctly implemented with zoom-scaled panning.
- **Distance-based opacity** via BFS is clean and readable.
- **ETL pipeline** is simple and effective — batch inserts with proper indexes.
- **`formatEtymologyText`** handles a messy, variable-format text field with reasonable heuristics.
- **Overall code density** is excellent — ~2500 lines total for a full-stack app with meaningful features.

---

## Priority Fix Order

| Priority | Finding | Reason |
|----------|---------|--------|
| 1        | S1      | Wheel listener leak — causes real UX degradation over time |
| 2        | M1      | Variable naming + potential `:` split bug in etymology links |
| 3        | S8      | XSS in search suggestions |
| 4        | M4      | Fragile edge label round-trip |
| 5        | S2      | Cognate expansion efficiency |
| 6        | S6      | Pin dependency versions |
