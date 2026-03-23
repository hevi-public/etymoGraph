from fastapi import APIRouter, HTTPException

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
async def get_word(word: str, lang: str = "English") -> dict:
    """Fetch a word entry with definitions, pronunciation, and etymology details."""
    col = get_words_collection()
    doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0})
    if not doc:
        normalized = normalize_word(word)
        if normalized != word:
            doc = await col.find_one({"word": normalized, "lang": lang}, {"_id": 0})
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
