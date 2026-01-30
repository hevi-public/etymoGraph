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
    "gmw-pro": "Proto-West Germanic",
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

    doc = await col.find_one({"word": word, "lang": lang}, {"_id": 0, "etymology_templates": 1})

    # Build root node
    root_id = node_id(word, lang)
    nodes[root_id] = {"id": root_id, "label": word, "language": lang, "level": 0}

    if not doc:
        return {"nodes": list(nodes.values()), "edges": edges}

    # Extract ancestry templates in order — they form a chain
    ancestry = []
    for tmpl in doc.get("etymology_templates", []):
        if tmpl.get("name") not in ANCESTRY_TYPES:
            continue
        args = tmpl.get("args", {})
        ancestor_lang_code = args.get("2", "")
        ancestor_word = args.get("3", "")
        if not ancestor_word or not ancestor_lang_code:
            continue
        ancestry.append({
            "word": ancestor_word,
            "lang": lang_name(ancestor_lang_code),
            "type": tmpl["name"],
        })

    # Chain them: word → ancestor1 → ancestor2 → ...
    prev_id = root_id
    for i, anc in enumerate(ancestry):
        if i >= max_depth:
            break
        aid = node_id(anc["word"], anc["lang"])
        if aid not in nodes:
            nodes[aid] = {"id": aid, "label": anc["word"], "language": anc["lang"], "level": i + 1}
        edges.append({
            "from": prev_id,
            "to": aid,
            "label": anc["type"],
        })
        prev_id = aid

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
    }
