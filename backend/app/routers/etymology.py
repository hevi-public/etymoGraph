from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorCollection

from app.database import get_words_collection
from app.services import lang_cache
from app.services.template_parser import (
    ANCESTRY_TYPES,
    COGNATE_TYPE,
    extract_ancestry,
    node_id,
    normalize_word,
)
from app.services.tree_builder import TreeBuilder

router = APIRouter()


@router.get("/etymology/{word}/chain")
async def get_etymology_chain(
    word: str,
    lang: str = "English",
    max_depth: int = 10,
    etym: int | None = None,
    col: AsyncIOMotorCollection = Depends(get_words_collection),
):
    """Trace ancestry chain upward from a word to its root."""
    await lang_cache.ensure_loaded(col)
    nodes = {}
    edges = []

    proj = {"_id": 0, "etymology_templates": 1}
    query = {"word": word, "lang": lang}
    if etym is not None:
        query["etymology_number"] = etym
    doc = await col.find_one(query, proj)
    if not doc:
        normalized = normalize_word(word)
        if normalized != word:
            nquery = {"word": normalized, "lang": lang}
            if etym is not None:
                nquery["etymology_number"] = etym
            doc = await col.find_one(nquery, proj)

    root_id = node_id(word, lang)
    nodes[root_id] = {"id": root_id, "label": word, "language": lang, "level": 0}

    if not doc:
        return {"nodes": list(nodes.values()), "edges": edges}

    ancestry = extract_ancestry(doc)

    prev_id = root_id
    for i, anc in enumerate(ancestry):
        if i >= max_depth:
            break
        aid = node_id(anc["word"], anc["lang"])
        if aid not in nodes:
            nodes[aid] = {
                "id": aid,
                "label": anc["word"],
                "language": anc["lang"],
                "level": -(i + 1),
            }
        edges.append({"from": aid, "to": prev_id, "label": anc["type"]})
        prev_id = aid

    return {"nodes": list(nodes.values()), "edges": edges}


@router.get("/etymology/{word}/tree")
async def get_etymology_tree(
    word: str,
    lang: str = "English",
    max_ancestor_depth: int = 10,
    max_descendant_depth: int = Query(3, ge=1, le=5),
    types: str = Query("inh", description="Comma-separated connection types: inh,bor,der,cog"),
    etym: int | None = None,
    col: AsyncIOMotorCollection = Depends(get_words_collection),
):
    """Build a full tree: trace up to the root, then find all descendants at each level."""
    await lang_cache.ensure_loaded(col)

    requested_types = set(types.split(",")) if types.strip() else set()
    include_cognates = COGNATE_TYPE in requested_types
    allowed_types = requested_types & ANCESTRY_TYPES

    # Only default to inh if nothing valid was requested at all
    if not allowed_types and not include_cognates:
        allowed_types = {"inh"}

    builder = TreeBuilder(col, allowed_types, max_ancestor_depth, max_descendant_depth)
    await builder.expand_word(word, lang, base_level=0, etym=etym)

    if include_cognates:
        await builder.expand_cognates()

    return builder.result()
