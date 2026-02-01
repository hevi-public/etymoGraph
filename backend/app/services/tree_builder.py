"""TreeBuilder: holds shared graph state and exposes methods for building etymology trees."""

from app.services import lang_cache
from app.services.template_parser import extract_ancestry, extract_cognates, node_id

MAX_DESCENDANTS_PER_NODE = 50
DEFAULT_MAX_COGNATE_ROUNDS = 2


class TreeBuilder:
    def __init__(self, col, allowed_types: set[str],
                 max_ancestor_depth: int, max_descendant_depth: int):
        self.col = col
        self.allowed_types = allowed_types
        self.max_ancestor_depth = max_ancestor_depth
        self.max_descendant_depth = max_descendant_depth
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.visited_edges: set[tuple] = set()

    def add_node(self, word: str, lang: str, level: int) -> str:
        nid = node_id(word, lang)
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "label": word, "language": lang, "level": level}
        return nid

    def add_edge(self, from_id: str, to_id: str, label: str) -> bool:
        """Add an edge if not already visited. Returns True if added."""
        edge_key = (from_id, to_id)
        if edge_key in self.visited_edges:
            return False
        self.visited_edges.add(edge_key)
        self.edges.append({"from": from_id, "to": to_id, "label": label})
        return True

    def result(self) -> dict:
        return {"nodes": list(self.nodes.values()), "edges": self.edges}

    async def expand_word(self, word: str, lang: str, base_level: int):
        """Trace ancestry upward and find descendants for a word."""
        self.add_node(word, lang, base_level)

        doc = await self.col.find_one(
            {"word": word, "lang": lang},
            {"_id": 0, "etymology_templates": 1},
        )
        if not doc:
            return

        chain = self._build_ancestor_chain(doc, word, lang, base_level)
        await self._expand_descendants_from_chain(chain)

    def _build_ancestor_chain(self, doc: dict, word: str, lang: str,
                              base_level: int) -> list[tuple]:
        """Trace ancestry upward, adding nodes/edges. Returns chain of (word, lang, lang_code, level)."""
        ancestry = extract_ancestry(doc, self.allowed_types)
        chain = [(word, lang, lang_cache.name_to_code(lang), base_level)]

        prev_id = node_id(word, lang)
        for i, anc in enumerate(ancestry):
            if i >= self.max_ancestor_depth:
                break
            aid = self.add_node(anc["word"], anc["lang"], base_level - (i + 1))
            self.add_edge(aid, prev_id, anc["type"])
            chain.append((anc["word"], anc["lang"], anc["lang_code"], base_level - (i + 1)))
            prev_id = aid

        return chain

    async def _expand_descendants_from_chain(self, chain: list[tuple]):
        """Find descendants from each node in the ancestor chain."""
        for anc_word, anc_lang, anc_lc, anc_level in chain:
            await self.find_descendants(anc_word, anc_lang, anc_lc, anc_level)

    async def find_descendants(self, word: str, lang: str, lc: str,
                               parent_level: int, depth: int = 0):
        """Find words that inherited/borrowed/derived from this word."""
        if depth >= self.max_descendant_depth:
            return

        parent_id = node_id(word, lang)

        cursor = self.col.find(
            {"etymology_templates": {"$elemMatch": {
                "name": {"$in": list(self.allowed_types)},
                "args.2": lc,
                "args.3": word,
            }}},
            {"_id": 0, "word": 1, "lang": 1, "lang_code": 1, "etymology_templates": 1},
        ).limit(MAX_DESCENDANTS_PER_NODE)

        docs = await cursor.to_list(length=MAX_DESCENDANTS_PER_NODE)

        seen = set()
        for doc in docs:
            dw = doc["word"]
            dl = doc["lang"]
            dlc = doc.get("lang_code", "")

            if (dw, dl) in seen:
                continue
            seen.add((dw, dl))

            # Only include if this ancestor is the IMMEDIATE parent
            first_ancestry = extract_ancestry(doc, self.allowed_types)
            if not first_ancestry or first_ancestry[0]["lang_code"] != lc or first_ancestry[0]["word"] != word:
                continue

            edge_type = first_ancestry[0]["type"]
            did = node_id(dw, dl)

            if not self.add_edge(did, parent_id, edge_type):
                continue

            self.add_node(dw, dl, parent_level + 1)
            await self.find_descendants(dw, dl, dlc, parent_level + 1, depth + 1)

    async def expand_cognates(self, max_rounds: int = DEFAULT_MAX_COGNATE_ROUNDS):
        """Expand cognates from all current nodes, recursively up to max_rounds."""
        processed_nids: set[str] = set()
        for _ in range(max_rounds):
            new_cognate_nodes = []

            # Snapshot: expand_word below adds new nodes
            unprocessed = [(nid, node) for nid, node in self.nodes.items()
                           if nid not in processed_nids]
            for nid, node in unprocessed:
                processed_nids.add(nid)
                doc = await self.col.find_one(
                    {"word": node["label"], "lang": node["language"]},
                    {"_id": 0, "etymology_templates": 1},
                )
                if not doc:
                    continue
                for cog in extract_cognates(doc):
                    cid = node_id(cog["word"], cog["lang"])
                    if not self.add_edge(nid, cid, "cog"):
                        continue
                    if cid not in self.nodes:
                        self.add_node(cog["word"], cog["lang"], node["level"])
                        new_cognate_nodes.append((cog["word"], cog["lang"]))

            if not new_cognate_nodes:
                break

            for cog_word, cog_lang in new_cognate_nodes:
                cog_level = self.nodes[node_id(cog_word, cog_lang)]["level"]
                await self.expand_word(cog_word, cog_lang, cog_level)
