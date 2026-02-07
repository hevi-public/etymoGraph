"""Language code <-> name cache backed by MongoDB languages collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection

_code_to_name: dict[str, str] = {}
_name_to_code: dict[str, str] = {}


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
    """Convert a language code to its display name, returning the code if unknown."""
    return _code_to_name.get(code, code)


def name_to_code(name: str) -> str:
    """Convert a language display name to its code, returning the name if unknown."""
    return _name_to_code.get(name, name)
