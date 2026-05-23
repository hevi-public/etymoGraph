"""Extract structured relationships from Kaikki etymology_templates."""

import unicodedata

from app.services import lang_cache

ANCESTRY_TYPES = {"inh", "bor", "der"}
COGNATE_TYPE = "cog"


def normalize_word(word: str) -> str:
    """Normalize template-form word to DB headword form.

    Handles two systematic mismatches (90.4% of broken links):
    - Strip leading '*' (reconstructed language convention): *wīną → wīną
    - NFKD decomposition + strip combining marks (macrons/diacritics): wīną → winą
    """
    if word.startswith("*"):
        word = word[1:]
    decomposed = unicodedata.normalize("NFKD", word)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def node_id(word: str, lang: str) -> str:
    return f"{word}:{lang}"


def extract_ancestry(doc: dict, allowed_types: set[str] | None = None) -> list[dict]:
    """Extract ordered ancestry templates from a document."""
    types = allowed_types or ANCESTRY_TYPES
    ancestry = []
    for tmpl in doc.get("etymology_templates", []):
        if tmpl.get("name") not in types:
            continue
        args = tmpl.get("args", {})
        ancestor_lang_code = args.get("2", "")
        ancestor_word = args.get("3", "")
        if not ancestor_word or not ancestor_lang_code:
            continue
        ancestry.append(
            {
                "word": ancestor_word,
                "lang": lang_cache.code_to_name(ancestor_lang_code),
                "lang_code": ancestor_lang_code,
                "type": tmpl["name"],
            }
        )
    return ancestry


def extract_cognates(doc: dict) -> list[dict]:
    """Extract cognate relationships from a document."""
    cognates = []
    for tmpl in doc.get("etymology_templates", []):
        if tmpl.get("name") != COGNATE_TYPE:
            continue
        args = tmpl.get("args", {})
        cog_lang_code = args.get("1", "")
        cog_word = args.get("2", "")
        if not cog_word or not cog_lang_code:
            continue
        cognates.append(
            {
                "word": cog_word,
                "lang": lang_cache.code_to_name(cog_lang_code),
                "lang_code": cog_lang_code,
            }
        )
    return cognates
