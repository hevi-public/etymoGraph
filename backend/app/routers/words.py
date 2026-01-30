from fastapi import APIRouter, HTTPException
from app.database import get_words_collection

router = APIRouter()


@router.get("/words/{word}")
async def get_word(word: str, lang: str = "English"):
    col = get_words_collection()
    doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Word '{word}' not found for language '{lang}'")

    glosses = []
    for sense in doc.get("senses", []):
        glosses.extend(sense.get("glosses", []))

    ipa = None
    for sound in doc.get("sounds", []):
        if "ipa" in sound:
            ipa = sound["ipa"]
            break

    return {
        "word": doc.get("word"),
        "lang": doc.get("lang"),
        "pos": doc.get("pos"),
        "definitions": glosses,
        "pronunciation": ipa,
        "etymology_text": doc.get("etymology_text"),
        "etymology_templates": doc.get("etymology_templates", []),
    }
