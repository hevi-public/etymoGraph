from fastapi import APIRouter
from app.database import get_words_collection

router = APIRouter()

# Template types that represent ancestry relationships
ANCESTRY_TYPES = {"inh", "bor", "der"}

LANG_CODE_MAP = {
    "en": "English",
    "enm": "Middle English",
    "ang": "Old English",
    "gem-pro": "Proto-Germanic",
    "ine-pro": "Proto-Indo-European",
    "la": "Latin",
    "itc-pro": "Proto-Italic",
    "grc": "Ancient Greek",
    "fro": "Old French",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "de": "German",
    "nl": "Dutch",
    "non": "Old Norse",
    "ar": "Arabic",
    "sa": "Sanskrit",
    "ja": "Japanese",
    "zh": "Chinese",
}


def lang_name(code):
    return LANG_CODE_MAP.get(code, code)


def node_id(word, lang):
    return f"{word}:{lang}"


@router.get("/etymology/{word}/chain")
async def get_etymology_chain(word: str, lang: str = "English", max_depth: int = 10):
    col = get_words_collection()
    nodes = {}
    edges = []
    visited = set()

    async def trace(w, l, level):
        nid = node_id(w, l)
        if nid in visited or level > max_depth:
            return
        visited.add(nid)

        nodes[nid] = {"id": nid, "label": w, "language": l, "level": level}

        doc = await col.find_one({"word": w, "lang": l}, {"_id": 0, "etymology_templates": 1})
        if not doc:
            return

        for tmpl in doc.get("etymology_templates", []):
            if tmpl.get("name") not in ANCESTRY_TYPES:
                continue
            args = tmpl.get("args", {})
            ancestor_lang_code = args.get("2", "")
            ancestor_word = args.get("3", "")
            if not ancestor_word or not ancestor_lang_code:
                continue

            ancestor_lang = lang_name(ancestor_lang_code)
            ancestor_id = node_id(ancestor_word, ancestor_lang)

            edges.append({
                "from": nid,
                "to": ancestor_id,
                "label": tmpl["name"],
            })

            await trace(ancestor_word, ancestor_lang, level + 1)

    await trace(word, lang, 0)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
    }
