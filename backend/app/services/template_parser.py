"""Extract structured relationships from Kaikki etymology_templates."""

import unicodedata

from app.services import lang_cache

ANCESTRY_TYPES = {"inh", "bor", "der"}
COGNATE_TYPE = "cog"

# Kaikki preserves the literal wikitext template name. Wiktionary editors
# sometimes spell out the full template name (`{{derived|...}}`) instead of
# using its short-form alias (`{{der|...}}`) — both render identically on
# Wiktionary and carry the same "derived from" meaning. Mirrors
# etymology_classifier.AFFIX_TEMPLATES's suf/suffix, pre/prefix aliasing.
ANCESTRY_TYPE_ALIASES = {"derived": "der"}


def expand_ancestry_types(types: set[str]) -> set[str]:
    """Expand canonical ancestry types to include their raw Kaikki template aliases."""
    return types | {
        alias for alias, canonical in ANCESTRY_TYPE_ALIASES.items() if canonical in types
    }


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
    match_types = expand_ancestry_types(types)
    ancestry = []
    for tmpl in doc.get("etymology_templates", []):
        name = tmpl.get("name")
        if name not in match_types:
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
                "type": ANCESTRY_TYPE_ALIASES.get(name, name),
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
