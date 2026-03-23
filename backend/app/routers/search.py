import re

from fastapi import APIRouter, Query

from app.database import get_words_collection

router = APIRouter()


async def _expand_polysemous(col, results: list[dict]) -> list[dict]:
    """Expand results that have multiple etymology_number values into separate entries.

    For each unique (word, lang) in results, check if distinct etymology groups
    exist. If 2+ groups found, replace single result with one per etymology,
    annotated with first_gloss for disambiguation.
    """
    expanded = []
    seen = set()

    for r in results:
        key = (r["word"], r["lang"])
        if key in seen:
            continue
        seen.add(key)

        # Check for multiple etymology groups
        pipeline = [
            {"$match": {"word": r["word"], "lang": r["lang"], "etymology_number": {"$exists": True}}},
            {"$sort": {"etymology_number": 1}},
            {"$group": {
                "_id": "$etymology_number",
                "pos_list": {"$addToSet": "$pos"},
                "first_gloss": {
                    "$first": {"$arrayElemAt": [{"$arrayElemAt": ["$senses.glosses", 0]}, 0]},
                },
            }},
            {"$sort": {"_id": 1}},
        ]
        groups = await col.aggregate(pipeline).to_list(length=20)

        if len(groups) >= 2:
            for g in groups:
                expanded.append({
                    "word": r["word"],
                    "lang": r["lang"],
                    "pos": ", ".join(sorted(g["pos_list"])),
                    "etymology_number": g["_id"],
                    "first_gloss": g.get("first_gloss", ""),
                })
        else:
            expanded.append(r)

    return expanded


@router.get("/search")
async def search_words(
    q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)
) -> dict:
    """Search words by exact match then prefix, deduplicated and merged."""
    col = get_words_collection()
    projection = {"_id": 0, "word": 1, "lang": 1, "pos": 1}

    # First: exact word matches (case-sensitive) — these are highest priority
    exact_cursor = col.find({"word": q}, projection).limit(limit)
    exact_results = await exact_cursor.to_list(length=limit)

    # Second: prefix matches (case-sensitive to use index) to fill remaining slots
    prefix_cursor = col.find(
        {"word": {"$regex": f"^{re.escape(q)}"}},
        projection,
    ).limit(limit * 3)
    prefix_results = await prefix_cursor.to_list(length=limit * 3)

    # Merge: exact first, then prefix, deduplicated by word+lang
    seen = set()
    unique = []
    for r in exact_results + prefix_results:
        key = (r["word"], r["lang"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
        if len(unique) >= limit:
            break

    # Expand polysemous exact matches (all results where word == q)
    exact_end = 0
    for r in unique:
        if r["word"] == q:
            exact_end += 1
        else:
            break
    if exact_end > 0:
        expanded = await _expand_polysemous(col, unique[:exact_end])
        unique = expanded + unique[exact_end:]

    return {"results": unique, "total": len(unique)}
