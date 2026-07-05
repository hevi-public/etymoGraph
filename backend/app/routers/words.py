from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorCollection

from app.database import get_words_collection
from app.services.etymology_classifier import classify_etymology, extract_word_mentions
from app.services.template_parser import normalize_word

router = APIRouter()


def extract_glosses(doc: dict) -> list[str]:
    """Extract all gloss strings from a Kaikki document's senses."""
    glosses = []
    for sense in doc.get("senses", []):
        glosses.extend(sense.get("glosses", []))
    return glosses


def extract_first_ipa(doc: dict) -> str | None:
    """Return the first IPA pronunciation from a document's sounds, or None."""
    for sound in doc.get("sounds", []):
        if "ipa" in sound:
            return sound["ipa"]
    return None


def extract_audio_urls(doc: dict) -> list[dict]:
    """Extract audio entries with ogg/mp3 URLs from a document's sounds."""
    audio = []
    for sound in doc.get("sounds", []):
        if "ogg_url" in sound or "mp3_url" in sound:
            entry = {}
            if "ogg_url" in sound:
                entry["ogg_url"] = sound["ogg_url"]
            if "mp3_url" in sound:
                entry["mp3_url"] = sound["mp3_url"]
            if "tags" in sound:
                entry["tags"] = sound["tags"]
            audio.append(entry)
    return audio


@router.get("/words/{word}")
async def get_word(
    word: str,
    lang: str = "English",
    etym: int | None = Query(None),
    col: AsyncIOMotorCollection = Depends(get_words_collection),
) -> dict:
    """Fetch a word entry with definitions, pronunciation, and etymology details."""
    query = {"word": word, "lang": lang}
    if etym is not None:
        query["etymology_number"] = etym
    doc = await col.find_one(query, {"_id": 0})
    if not doc:
        normalized = normalize_word(word)
        if normalized != word:
            nquery = {"word": normalized, "lang": lang}
            if etym is not None:
                nquery["etymology_number"] = etym
            doc = await col.find_one(nquery, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"Word '{word}' not found for language '{lang}'"
        )

    uncertainty = classify_etymology(doc)
    mentions = extract_word_mentions(doc)

    phonetic = doc.get("phonetic", {})

    return {
        "word": doc.get("word"),
        "lang": doc.get("lang"),
        "pos": doc.get("pos"),
        "definitions": extract_glosses(doc),
        "pronunciation": extract_first_ipa(doc),
        "etymology_text": doc.get("etymology_text"),
        "etymology_templates": doc.get("etymology_templates", []),
        "etymology_uncertainty": uncertainty.to_dict(),
        "related_mentions": [m.to_dict() for m in mentions],
        "audio": extract_audio_urls(doc),
        "phonetic_ipa": phonetic.get("ipa"),
        "dolgo_classes": phonetic.get("dolgo_classes"),
        "dolgo_consonants": phonetic.get("dolgo_consonants"),
    }
