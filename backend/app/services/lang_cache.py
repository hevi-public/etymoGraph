"""Language code <-> name cache backed by MongoDB languages collection.

The `languages` collection is built by `etl/load.py` from the unique
(lang_code, lang) pairs found on words whose `lang` field exists. Wiktionary
uses many sub-language codes (chronological registers, dialects, proto-stage
variants) that are referenced from `etymology_templates.args` but never appear
as the primary `lang_code` of a word in our dump. Those codes have no entry in
`languages` and would leak into the API as raw codes (e.g. `la-med` instead of
"Medieval Latin").

`_EXTENDED_CODES` is a hand-curated fallback for those cases. The lookup chain
is: dynamic cache (Kaikki-derived) → static fallback → raw code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection

_code_to_name: dict[str, str] = {}
_name_to_code: dict[str, str] = {}

# Wiktionary sub-language codes commonly referenced from etymology templates
# but absent from the auto-built `languages` collection. Add codes here as you
# observe raw codes leaking into graph node IDs.
#
# Source: en.wiktionary.org/wiki/Module:languages and adjacent etymology
# modules. Keep names verbatim with what Wiktionary's module uses so cross-
# referencing stays straightforward.
_EXTENDED_CODES: dict[str, str] = {
    # Latin chronological / register variants
    "la-med": "Medieval Latin",
    "la-lat": "Late Latin",
    "la-ecc": "Ecclesiastical Latin",
    "la-vul": "Vulgar Latin",
    "la-cla": "Classical Latin",
    "la-new": "New Latin",
    # Romance stages and dialects
    "roa-oit": "Old Italian",
    "roa-opt": "Old Portuguese",
    "roa-onf": "Old Northern French",
    "xno": "Anglo-Norman",
    "fro": "Old French",
    "frm": "Middle French",
    # Iranian
    "fa-cls": "Early Classical Persian",
    "fa-ira": "Iranian Persian",
    "fa-dar": "Dari Persian",
    "peo": "Old Persian",
    "pal": "Middle Persian",
    # Germanic stages
    "gmw-pro": "Proto-West Germanic",
    "gem-pro": "Proto-Germanic",
    "gmh": "Middle High German",
    "goh": "Old High German",
    "gml": "Middle Low German",
    # PIE and adjacent
    "ine-pro": "Proto-Indo-European",
    "itc-pro": "Proto-Italic",
    "cel-pro": "Proto-Celtic",
    "sla-pro": "Proto-Slavic",
    # Greek registers
    "grc-koi": "Koine Greek",
    "grc-byz": "Byzantine Greek",
    # Arabic dialects
    "ar-and": "Andalusian Arabic",
    "afb": "Gulf Arabic",
    # Sentinel
    "und": "Undetermined",
}


async def ensure_loaded(col: AsyncIOMotorCollection) -> None:
    """Build lang code/name cache from the precomputed languages collection."""
    if _code_to_name:
        return
    lang_col = col.database.get_collection("languages")
    cursor = lang_col.find({}, {"_id": 0, "lang_code": 1, "lang": 1})
    async for doc in cursor:
        code = doc.get("lang_code", "")
        name = doc.get("lang", "")
        if code and name:
            _code_to_name[code] = name
            _name_to_code[name] = code


def code_to_name(code: str) -> str:
    """Convert a language code to its display name.

    Lookup order: dynamic cache (loaded from `languages` collection) → static
    extended-codes fallback → the raw input code.
    """
    if code in _code_to_name:
        return _code_to_name[code]
    return _EXTENDED_CODES.get(code, code)


def name_to_code(name: str) -> str:
    """Convert a language display name to its code, returning the name if unknown."""
    if name in _name_to_code:
        return _name_to_code[name]
    # Reverse fallback through the extended codes. First match wins (the
    # dict is small enough that scanning is cheap).
    for code, ext_name in _EXTENDED_CODES.items():
        if ext_name == name:
            return code
    return name
