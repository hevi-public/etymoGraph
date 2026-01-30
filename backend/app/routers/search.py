from fastapi import APIRouter, HTTPException, Query
from app.database import get_words_collection

router = APIRouter()


@router.get("/search")
async def search_words(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    col = get_words_collection()

    # Try prefix regex match (faster for autocomplete)
    cursor = col.find(
        {"word": {"$regex": f"^{q}", "$options": "i"}, "lang": "English"},
        {"_id": 0, "word": 1, "lang": 1, "pos": 1},
    ).limit(limit)

    results = await cursor.to_list(length=limit)

    # Deduplicate by word (multiple POS entries)
    seen = set()
    unique = []
    for r in results:
        if r["word"] not in seen:
            seen.add(r["word"])
            unique.append(r)

    return {"results": unique, "total": len(unique)}
