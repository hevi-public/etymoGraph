from fastapi import APIRouter, Query
from app.database import get_words_collection

router = APIRouter()

ANCESTRY_TYPES = {"inh", "bor", "der"}
COGNATE_TYPE = "cog"
ALL_EDGE_TYPES = ANCESTRY_TYPES | {COGNATE_TYPE}


# Cache for lang code <-> name lookups from DB
_lang_code_to_name = {}
_lang_name_to_code = {}


async def _ensure_lang_cache(col):
    """Build lang code/name cache from the precomputed languages collection."""
    if _lang_code_to_name:
        return
    lang_col = col.database.get_collection("languages")
    cursor = lang_col.find({}, {"_id": 0, "lang_code": 1, "lang": 1})
    async for doc in cursor:
        code = doc.get("lang_code", "")
        name = doc.get("lang", "")
        if code and name:
            _lang_code_to_name[code] = name
            _lang_name_to_code[name] = code


def lang_name(code):
    return _lang_code_to_name.get(code, code)


def lang_code(name):
    return _lang_name_to_code.get(name, name)


def node_id(word, lang):
    return f"{word}:{lang}"


@router.get("/etymology/{word}/chain")
async def get_etymology_chain(word: str, lang: str = "English", max_depth: int = 10):
    """Trace ancestry chain upward from a word to its root."""
    col = get_words_collection()
    await _ensure_lang_cache(col)
    nodes = {}
    edges = []

    doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0, "etymology_templates": 1})

    root_id = node_id(word, lang)
    nodes[root_id] = {"id": root_id, "label": word, "language": lang, "level": 0}

    if not doc:
        return {"nodes": list(nodes.values()), "edges": edges}

    ancestry = _extract_ancestry(doc)

    prev_id = root_id
    for i, anc in enumerate(ancestry):
        if i >= max_depth:
            break
        aid = node_id(anc["word"], anc["lang"])
        if aid not in nodes:
            nodes[aid] = {"id": aid, "label": anc["word"], "language": anc["lang"], "level": i + 1}
        edges.append({"from": prev_id, "to": aid, "label": anc["type"]})
        prev_id = aid

    return {"nodes": list(nodes.values()), "edges": edges}


@router.get("/etymology/{word}/tree")
async def get_etymology_tree(
    word: str,
    lang: str = "English",
    max_ancestor_depth: int = 10,
    max_descendant_depth: int = Query(3, ge=1, le=5),
    types: str = Query("inh", description="Comma-separated connection types: inh,bor,der,cog"),
):
    """Build a full tree: trace up to the root, then find all descendants at each level."""
    col = get_words_collection()
    await _ensure_lang_cache(col)
    nodes = {}
    edges = []
    visited_edges = set()
    requested_types = set(types.split(","))
    include_cognates = COGNATE_TYPE in requested_types
    allowed_types = requested_types & ANCESTRY_TYPES

    if not allowed_types:
        allowed_types = {"inh"}

    # Step 1: Build ancestry + descendants for the searched word
    await _expand_word(
        col, word, lang, 0, nodes, edges, visited_edges,
        max_ancestor_depth, max_descendant_depth, allowed_types,
    )

    # Step 2: Add cognates if requested, and expand each cognate's tree too
    if include_cognates:
        await _expand_cognates(
            col, nodes, edges, visited_edges,
            max_ancestor_depth, max_descendant_depth, allowed_types,
            max_cognate_depth=2,  # how many rounds of cognate expansion
        )

    return {"nodes": list(nodes.values()), "edges": edges}


async def _expand_word(col, word, lang, base_level, nodes, edges, visited_edges,
                       max_ancestor_depth, max_descendant_depth, allowed_types):
    """Trace ancestry upward and find descendants for a word."""
    root_id = node_id(word, lang)
    if root_id not in nodes:
        nodes[root_id] = {"id": root_id, "label": word, "language": lang, "level": base_level}

    doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0, "etymology_templates": 1})
    if not doc:
        return

    ancestry = _extract_ancestry(doc, allowed_types)

    # Build ancestor chain
    ancestor_chain = [(word, lang, lang_code(lang), base_level)]
    prev_id = root_id
    for i, anc in enumerate(ancestry):
        if i >= max_ancestor_depth:
            break
        aid = node_id(anc["word"], anc["lang"])
        level = base_level - (i + 1)
        if aid not in nodes:
            nodes[aid] = {"id": aid, "label": anc["word"], "language": anc["lang"], "level": level}
        edge_key = (aid, prev_id)
        if edge_key not in visited_edges:
            visited_edges.add(edge_key)
            edges.append({"from": aid, "to": prev_id, "label": anc["type"]})
        ancestor_chain.append((anc["word"], anc["lang"], anc["lang_code"], level))
        prev_id = aid

    # Find descendants from each ancestor
    for anc_word, anc_lang, anc_lc, anc_level in ancestor_chain:
        await _find_descendants(
            col, anc_word, anc_lang, anc_lc, anc_level,
            nodes, edges, visited_edges,
            max_descendant_depth, 0, allowed_types,
        )


async def _expand_cognates(col, nodes, edges, visited_edges,
                           max_ancestor_depth, max_descendant_depth, allowed_types,
                           max_cognate_depth):
    """Expand cognates from all current nodes, recursively up to max_cognate_depth rounds."""
    processed_nids = set()
    for _ in range(max_cognate_depth):
        new_cognate_nodes = []

        # Only query nodes not yet processed for cognates
        unprocessed = [(nid, node) for nid, node in nodes.items() if nid not in processed_nids]
        for nid, node in unprocessed:
            processed_nids.add(nid)
            doc = await col.find_one(
                {"word": node["label"], "lang": node["language"]},
                {"_id": 0, "etymology_templates": 1},
            )
            if not doc:
                continue
            for cog in _extract_cognates(doc):
                cid = node_id(cog["word"], cog["lang"])
                edge_key = (nid, cid)
                if edge_key in visited_edges:
                    continue
                visited_edges.add(edge_key)
                is_new = cid not in nodes
                if is_new:
                    nodes[cid] = {"id": cid, "label": cog["word"], "language": cog["lang"], "level": node["level"]}
                    new_cognate_nodes.append((cog["word"], cog["lang"]))
                edges.append({"from": nid, "to": cid, "label": "cog"})

        if not new_cognate_nodes:
            break

        # Expand ancestry + descendants for newly added cognate nodes
        for cog_word, cog_lang in new_cognate_nodes:
            await _expand_word(
                col, cog_word, cog_lang, nodes[node_id(cog_word, cog_lang)]["level"],
                nodes, edges, visited_edges,
                max_ancestor_depth, max_descendant_depth, allowed_types,
            )


async def _find_descendants(col, word, lang, lc, parent_level, nodes, edges, visited_edges, max_depth, current_depth, allowed_types):
    """Find words that inherited/borrowed/derived from this word."""
    if current_depth >= max_depth:
        return

    parent_id = node_id(word, lang)

    # Query: find documents whose etymology_templates reference this word as ancestor
    cursor = col.find(
        {"etymology_templates": {"$elemMatch": {
            "name": {"$in": list(allowed_types)},
            "args.2": lc,
            "args.3": word,
        }}},
        {"_id": 0, "word": 1, "lang": 1, "lang_code": 1, "etymology_templates": 1},
    ).limit(50)  # Cap to prevent explosion

    docs = await cursor.to_list(length=50)

    # Deduplicate by word+lang
    seen = set()
    for doc in docs:
        dw = doc["word"]
        dl = doc["lang"]
        dlc = doc.get("lang_code", "")
        did = node_id(dw, dl)

        if (dw, dl) in seen:
            continue
        seen.add((dw, dl))

        # Only include if this ancestor is the IMMEDIATE parent
        # (first ancestry template in the descendant's chain)
        first_ancestry = _extract_ancestry(doc, allowed_types)
        if not first_ancestry or first_ancestry[0]["lang_code"] != lc or first_ancestry[0]["word"] != word:
            continue

        edge_type = first_ancestry[0]["type"]

        edge_key = (did, parent_id)
        if edge_key in visited_edges:
            continue
        visited_edges.add(edge_key)

        if did not in nodes:
            nodes[did] = {"id": did, "label": dw, "language": dl, "level": parent_level + 1}

        edges.append({"from": parent_id, "to": did, "label": edge_type})

        # Recurse to find this descendant's descendants
        await _find_descendants(
            col, dw, dl, dlc, parent_level + 1,
            nodes, edges, visited_edges,
            max_depth, current_depth + 1, allowed_types,
        )


def _extract_cognates(doc):
    """Extract cognate relationships from a document."""
    cognates = []
    for tmpl in doc.get("etymology_templates", []):
        if tmpl.get("name") != COGNATE_TYPE:
            continue
        args = tmpl.get("args", {})
        cog_lang_code = args.get("1", "")
        cog_word = args.get("2", "")
        if not cog_word or not cog_lang_code:
            continue
        cognates.append({
            "word": cog_word,
            "lang": lang_name(cog_lang_code),
            "lang_code": cog_lang_code,
        })
    return cognates


def _extract_ancestry(doc, allowed_types=None):
    """Extract ordered ancestry templates from a document."""
    types = allowed_types or ANCESTRY_TYPES
    ancestry = []
    for tmpl in doc.get("etymology_templates", []):
        if tmpl.get("name") not in types:
            continue
        args = tmpl.get("args", {})
        ancestor_lang_code = args.get("2", "")
        ancestor_word = args.get("3", "")
        if not ancestor_word or not ancestor_lang_code:
            continue
        ancestry.append({
            "word": ancestor_word,
            "lang": lang_name(ancestor_lang_code),
            "lang_code": ancestor_lang_code,
            "type": tmpl["name"],
        })
    return ancestry
