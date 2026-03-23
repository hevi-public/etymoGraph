# Decision Log: SPC-00012 Precompute Compound/Affix Edges

## Starting Question

When tracing "window" through the etymology graph, the chain reaches Old Norse "vindauga" — a compound of "vindr" (wind) + "auga" (eye). But the compound structure was never shown because `tree_builder.py` only expanded compounds for words with no ancestry (the `len(chain) == 1` gate). How can we properly display compound decomposition for any word in the chain?

## Alternatives Considered

### Option A: Expand mention edges for ancestor chain endpoints only

When the topmost ancestor has no further ancestry, call `_add_mention_edges` on it.

- **Pros:** Minimal code change, reuses existing logic
- **Cons:** Only works at chain endpoints, doesn't catch compounds in the middle of chains. Still query-time template parsing.

### Option B: Precompute compound edges at ETL time (chosen)

Scan all documents with compound/affix templates during ETL, store edges in a dedicated collection, and have the tree builder query precomputed edges for all ancestor nodes.

- **Pros:** Fast query-time lookups, works for any node in the chain, enables recursive component ancestry tracing, validates component existence upfront
- **Cons:** Additional ETL step, new collection to maintain

### Option C: Expand all ancestor nodes at query time

Run `_add_mention_edges` on every node in the ancestor chain, not just the leaf.

- **Pros:** No new ETL step
- **Cons:** Expensive at query time (N DB lookups per request per ancestor), potentially noisy with non-compound mentions

## Decision & Rationale

**Option B** was chosen because:

1. **Performance:** Precomputation moves the expensive work (template parsing, word existence validation, language resolution) to a one-time batch job. Query-time lookups become simple indexed queries.
2. **Completeness:** The precomputed collection covers all 1.17M compound-bearing documents with validated existence flags, vs. discovering issues one word at a time.
3. **Separation of concerns:** ETL produces edges, tree builder consumes them. The extraction constants (`AFFIX_TEMPLATES`, `normalize_word`) are imported from their canonical locations.
4. **Precedent:** Follows the established `precompute_phonetic.py` pattern for ETL enrichment.

### Sub-decision: Forward pass vs. bottom-up root discovery

The user suggested identifying "root" nodes (no further dependencies) and working back. A forward pass over compound-bearing documents was chosen instead because each document already declares its components — no graph traversal needed to discover roots. The precomputed edges collection enables the same instant lookups.

### Sub-decision: Ancestry tracing for components

Components' own ancestry chains are traced upward at query time (reusing `_build_ancestor_chain`), depth-limited to 2 levels. This produces the full parallel lineage (e.g., vindr → *windaz → PIE alongside auga → *augô → PIE) without precomputing transitive closures.

## Participants

- **Human:** Identified the compound display problem with "window", proposed bottom-up precomputation approach
- **Claude (DA):** Researched Kaikki data structure, designed and implemented the ETL + tree builder changes
