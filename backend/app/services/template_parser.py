"""Extract structured relationships from Kaikki etymology_templates."""

from app.services import lang_cache

ANCESTRY_TYPES = {"inh", "bor", "der"}
COGNATE_TYPE = "cog"


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
        ancestry.append({
            "word": ancestor_word,
            "lang": lang_cache.code_to_name(ancestor_lang_code),
            "lang_code": ancestor_lang_code,
            "type": tmpl["name"],
        })
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
        cognates.append({
            "word": cog_word,
            "lang": lang_cache.code_to_name(cog_lang_code),
            "lang_code": cog_lang_code,
        })
    return cognates
