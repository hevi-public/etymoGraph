from fastapi import APIRouter, HTTPException
from app.database import get_words_collection

router = APIRouter()


def extract_glosses(doc: dict) -> list[str]:
    glosses = []
    for sense in doc.get("senses", []):
        glosses.extend(sense.get("glosses", []))
    return glosses


def extract_first_ipa(doc: dict) -> str | None:
    for sound in doc.get("sounds", []):
        if "ipa" in sound:
            return sound["ipa"]
    return None


@router.get("/words/{word}")
async def get_word(word: str, lang: str = "English"):
    col = get_words_collection()
    doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Word '{word}' not found for language '{lang}'")

    return {
        "word": doc.get("word"),
        "lang": doc.get("lang"),
        "pos": doc.get("pos"),
        "definitions": extract_glosses(doc),
        "pronunciation": extract_first_ipa(doc),
        "etymology_text": doc.get("etymology_text"),
        "etymology_templates": doc.get("etymology_templates", []),
    }
