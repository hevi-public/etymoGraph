# Decision Log: SPC-00017 Graph Export & Interoperability

## Starting Question

The tool can't export anything. What export surface serves both a hobbyist who wants to share a
picture and a linguist who wants to analyze the data in standard tools — without overbuilding?

## Alternatives Considered

### Option A: Image export only (PNG)
- **Pros:** Easiest; covers the share-a-picture case.
- **Cons:** Useless to researchers; throws away the structured data the app already has.

### Option B: One generic data format (JSON) only
- **Pros:** Trivial (it's the API's internal shape).
- **Cons:** Researchers live in Gephi / phylogenetics / CLDF ecosystems; raw JSON makes them write
  converters. Misses the interoperability point.

### Option C: Image + a curated set of standard formats (chosen)
PNG/SVG for sharing; GraphML/GEXF (Gephi), Newick/Nexus (phylogenetics), CLDF (comparative
linguistics), JSON (raw).
- **Pros:** Each target audience gets a first-class path; formats are well-specified and stable.
- **Cons:** More serializers to write and test.

## Decision & Rationale

**Option C.** Export is precisely the seam where the linguist/hobbyist split is widest, so a single
format can't serve both. The chosen set maps to the actual ecosystems each audience uses. Newick is
explicitly scoped to the **inheritance spanning tree** (the full graph has cognate/borrowing
cross-links and isn't a tree) to avoid misrepresenting the data. The heavier static-site and bulk
exports (N2.5/N2.6) are deferred but are natural extensions of the per-graph JSON/image primitives
defined here.

## Participants

- **Human:** Approved a roadmap explicitly serving linguists and hobbyists alike.
- **Claude (DA):** Mapped export formats to each audience's tooling and scoped Newick's tree
  projection honestly.
