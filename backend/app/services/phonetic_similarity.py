"""Phonetic similarity computation using Dolgopolsky sound classes.

Pure functions with no database dependency. Used by the concept map router
to compute pairwise similarity edges and Turchin clusters.
"""

from app.services.template_parser import node_id


def dolgopolsky_distance(cc1: str, cc2: str) -> float:
    """Normalized Levenshtein distance between consonant class strings.

    Returns 0.0 (identical) to 1.0 (completely different).
    """
    if not cc1 and not cc2:
        return 0.0
    if not cc1 or not cc2:
        return 1.0

    n, m = len(cc1), len(cc2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if cc1[i - 1] == cc2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )

    max_len = max(n, m)
    return dp[n][m] / max_len if max_len > 0 else 0.0


def build_similarity_edges(words: list[dict], threshold: float = 0.3) -> list[dict]:
    """Compute pairwise phonetic similarity for all words.

    Returns edges above the threshold floor. The frontend applies its own
    slider-based filtering on top of this.
    """
    edges = []
    for i in range(len(words)):
        cc_i = words[i].get("dolgo_consonants", "")
        f2_i = words[i].get("dolgo_first2", "")
        id_i = words[i]["id"]

        for j in range(i + 1, len(words)):
            cc_j = words[j].get("dolgo_consonants", "")
            f2_j = words[j].get("dolgo_first2", "")

            if not cc_i or not cc_j:
                continue

            sim = 1.0 - dolgopolsky_distance(cc_i, cc_j)
            turchin = len(f2_i) >= 2 and len(f2_j) >= 2 and f2_i == f2_j

            if sim >= threshold or turchin:
                edges.append(
                    {
                        "source": id_i,
                        "target": words[j]["id"],
                        "similarity": round(sim, 3),
                        "turchin_match": turchin,
                        "shared_classes": _shared_prefix(cc_i, cc_j),
                    }
                )

    return edges


def build_clusters(words: list[dict]) -> list[dict]:
    """Group words by their first two Dolgopolsky consonant classes (Turchin clusters)."""
    groups: dict[str, list[str]] = {}
    for w in words:
        f2 = w.get("dolgo_first2", "")
        if len(f2) >= 2:
            groups.setdefault(f2, []).append(w["id"])

    return [
        {
            "id": f"cluster_{key}",
            "label": f"{'-'.join(key)} group",
            "words": ids,
        }
        for key, ids in sorted(groups.items())
        if len(ids) >= 2
    ]


def format_word_for_response(doc: dict) -> dict:
    """Transform a MongoDB document into a concept map word entry."""
    phonetic = doc.get("phonetic", {})
    word = doc.get("word", "")
    lang = doc.get("lang", "")
    return {
        "id": node_id(word, lang),
        "word": word,
        "lang": lang,
        "lang_code": doc.get("lang_code", ""),
        "pos": doc.get("pos", ""),
        "ipa": phonetic.get("ipa", ""),
        "dolgo_classes": phonetic.get("dolgo_classes", ""),
        "dolgo_consonants": phonetic.get("dolgo_consonants", ""),
        "dolgo_first2": phonetic.get("dolgo_first2", ""),
        "has_etymology": bool(doc.get("etymology_text")),
        "etymology_summary": _etymology_summary(doc),
    }


def _shared_prefix(cc1: str, cc2: str) -> str:
    """Return the longest shared prefix of two consonant class strings."""
    prefix = []
    for a, b in zip(cc1, cc2, strict=False):
        if a == b:
            prefix.append(a)
        else:
            break
    return "".join(prefix)


def _etymology_summary(doc: dict) -> str:
    """Extract a short etymology summary from the first ancestry template."""
    for tmpl in doc.get("etymology_templates", []):
        if tmpl.get("name") in ("inh", "bor", "der"):
            expansion = tmpl.get("expansion", "")
            if expansion:
                return expansion[:120]
    text = doc.get("etymology_text", "")
    if text:
        return text[:120]
    return ""
