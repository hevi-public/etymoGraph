"""Concept map API endpoints for phonetic similarity visualization."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query

from app.database import get_words_collection
from app.services.concept_resolver import resolve_concept, suggest_concepts
from app.services.phonetic_similarity import (
    build_clusters,
    format_word_for_response,
)
from app.services.template_parser import COGNATE_TYPE, node_id

router = APIRouter()


@router.get("/concept-map")
async def get_concept_map(
    concept: str = Query(..., description="The concept to map (e.g. 'fire')"),
    pos: str | None = Query(None, description="Part of speech filter"),
    include_etymology_edges: bool = Query(
        True, description="Include known etymological connections"
    ),
) -> dict:
    """Build a concept map with phonetic similarity edges for a given concept."""
    col = get_words_collection()

    docs, resolution_method = await resolve_concept(col, concept, pos)

    if not docs:
        raise HTTPException(
            status_code=404,
            detail=f"No words with phonetic data found for concept '{concept}'",
        )

    words = [format_word_for_response(doc) for doc in docs]

    # Turchin clusters
    clusters = build_clusters(words)

    # Etymology edges between concept map words
    etymology_edges = []
    if include_etymology_edges:
        etymology_edges = _extract_etymology_edges(docs, words)

    return {
        "concept": concept,
        "resolution_method": resolution_method,
        "word_count": len(words),
        "words": words,
        "phonetic_edges": [],  # computed client-side in Web Worker
        "etymology_edges": etymology_edges,
        "clusters": clusters,
    }


@router.get("/concepts/suggest")
async def get_concept_suggestions(
    q: str = Query(..., min_length=1, description="Partial concept name"),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Autocomplete endpoint for concept search."""
    col = get_words_collection()
    suggestions = await suggest_concepts(col, q, limit)
    return {"suggestions": suggestions}


def _add_edge(
    source_id: str,
    target_id: str,
    relationship: str,
    edges: list[dict],
    seen: set[tuple[str, str]],
) -> None:
    """Add a deduplicated edge to the edge list."""
    edge_key = tuple(sorted([source_id, target_id]))
    if edge_key not in seen:
        seen.add(edge_key)
        edges.append({"source": source_id, "target": target_id, "relationship": relationship})


def _extract_etymology_edges(docs: list[dict], words: list[dict]) -> list[dict]:
    """Find etymological connections between words in the concept map.

    Uses cognate templates and text-based matching between word pairs.
    Dict-based lookups replace O(n) inner scans for cognate matching.
    """
    # word name → list of (word, lang) pairs for O(1) cognate lookup
    words_by_name: dict[str, list[tuple[str, str]]] = defaultdict(list)
    word_id_lookup: dict[tuple[str, str], str] = {}
    for w in words:
        key = (w["word"], w["lang"])
        words_by_name[w["word"]].append(key)
        word_id_lookup[key] = w["id"]

    word_set = set(word_id_lookup.keys())
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    for doc in docs:
        doc_word = doc.get("word", "")
        doc_lang = doc.get("lang", "")
        source_id = node_id(doc_word, doc_lang)

        # Check cognate templates — dict lookup instead of scanning word_set
        for tmpl in doc.get("etymology_templates", []):
            if tmpl.get("name") != COGNATE_TYPE:
                continue
            cog_word = tmpl.get("args", {}).get("2", "")
            for target_word, target_lang in words_by_name.get(cog_word, []):
                if (target_word, target_lang) != (doc_word, doc_lang):
                    target_id = word_id_lookup[(target_word, target_lang)]
                    _add_edge(source_id, target_id, "cognate", edges, seen_edges)

        # Check etymology text for mentions of other words in the set
        etym_text = doc.get("etymology_text", "")
        if etym_text:
            for target_word, target_lang in word_set:
                if (target_word, target_lang) == (doc_word, doc_lang):
                    continue
                if len(target_word) >= 3 and target_word in etym_text:
                    target_id = word_id_lookup[(target_word, target_lang)]
                    _add_edge(source_id, target_id, "mentioned", edges, seen_edges)

    return edges
