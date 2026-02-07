import re

from fastapi import APIRouter, Query

from app.database import get_words_collection

router = APIRouter()


@router.get("/search")
async def search_words(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
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

    return {"results": unique, "total": len(unique)}
