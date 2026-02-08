"""Concept map API endpoints for phonetic similarity visualization."""

from fastapi import APIRouter, HTTPException, Query

from app.database import get_words_collection
from app.services.concept_resolver import resolve_concept, suggest_concepts
from app.services.phonetic_similarity import (
    build_clusters,
    build_similarity_edges,
    format_word_for_response,
)
from app.services.template_parser import COGNATE_TYPE, node_id

router = APIRouter()


@router.get("/concept-map")
async def get_concept_map(
    concept: str = Query(..., description="The concept to map (e.g. 'fire')"),
    pos: str | None = Query(None, description="Part of speech filter"),
    max_words: int = Query(0, ge=0, description="Max words to include (0 = unlimited)"),
    include_etymology_edges: bool = Query(
        True, description="Include known etymological connections"
    ),
) -> dict:
    """Build a concept map with phonetic similarity edges for a given concept."""
    col = get_words_collection()

    docs, resolution_method = await resolve_concept(col, concept, pos, max_words)

    if not docs:
        raise HTTPException(
            status_code=404,
            detail=f"No words with phonetic data found for concept '{concept}'",
        )

    words = [format_word_for_response(doc) for doc in docs]

    # Phonetic similarity edges (floor at 0.3, frontend filters further)
    phonetic_edges = build_similarity_edges(words, threshold=0.3)

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
        "phonetic_edges": phonetic_edges,
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


def _extract_etymology_edges(docs: list[dict], words: list[dict]) -> list[dict]:
    """Find etymological connections between words in the concept map.

    Uses cognate templates and text-based matching between word pairs.
    """
    word_set = {(w["word"], w["lang"]) for w in words}
    word_id_lookup = {(w["word"], w["lang"]): w["id"] for w in words}
    edges = []
    seen_edges: set[tuple[str, str]] = set()

    for doc in docs:
        doc_word = doc.get("word", "")
        doc_lang = doc.get("lang", "")
        source_id = node_id(doc_word, doc_lang)

        # Check cognate templates
        for tmpl in doc.get("etymology_templates", []):
            if tmpl.get("name") != COGNATE_TYPE:
                continue
            args = tmpl.get("args", {})
            cog_word = args.get("2", "")
            # Try to find the cognate in our word set
            for target_word, target_lang in word_set:
                if target_word == cog_word and (doc_word, doc_lang) != (
                    target_word,
                    target_lang,
                ):
                    target_id = word_id_lookup[(target_word, target_lang)]
                    edge_key = tuple(sorted([source_id, target_id]))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append(
                            {
                                "source": source_id,
                                "target": target_id,
                                "relationship": "cognate",
                            }
                        )

        # Check etymology text for mentions of other words in the set
        etym_text = doc.get("etymology_text", "")
        if etym_text:
            for target_word, target_lang in word_set:
                if (target_word, target_lang) == (doc_word, doc_lang):
                    continue
                if len(target_word) < 3:
                    continue
                if target_word in etym_text:
                    target_id = word_id_lookup[(target_word, target_lang)]
                    edge_key = tuple(sorted([source_id, target_id]))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append(
                            {
                                "source": source_id,
                                "target": target_id,
                                "relationship": "mentioned",
                            }
                        )

    return edges
