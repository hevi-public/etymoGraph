# SPC-00002: Concept Map — Phonetic Similarity Visualization by Semantic Field

| Field | Value |
|---|---|
| **Status** | implemented |
| **Created** | 2026-02-07 |
| **Modifies** | — |
| **Modified-by** | SPC-00003 (adds URL routing for concept map state) |

---

## 1. Purpose

The Concept Map is a visualization that answers: **"What do languages call this concept, and which ones sound similar?"**

Given a semantic concept (e.g., "fire", "water", "hand"), the tool:

1. Retrieves all words across all languages that express that concept
2. Computes phonetic similarity between every pair using Dolgopolsky sound classes
3. Displays them as a force-directed graph where **phonetic similarity determines proximity** (not etymological relationship)
4. Optionally overlays known etymological connections

This is a **neutral discovery tool** — the algorithm places words, the user observes patterns.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (vis.js)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Concept      │  │ Force-directed│  │ Detail Panel  │  │
│  │ Search Bar   │  │ Graph Canvas  │  │ (right side)  │  │
│  └──────┬──────┘  └──────────────┘  └───────────────┘  │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │ GET /api/concept-map?concept=fire
          ▼
┌─────────────────────────────────────────────────────────┐
│                  Python Backend (Flask/FastAPI)          │
│  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │ Concept Resolver  │  │ Similarity Matrix Builder   │  │
│  │ (find all words   │  │ (Dolgopolsky classes →      │  │
│  │  for a concept)   │  │  pairwise distances)        │  │
│  └────────┬─────────┘  └─────────────────────────────┘  │
│           │                                              │
└───────────┼──────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────┐
│              MongoDB (kaikki.org Wiktionary dump)        │
│  - entries collection (word, lang, sounds, senses, etc) │
│  - phonetic subdocument (precomputed sound classes)      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Data Pipeline

### 3.1 Prerequisite: Precomputed Sound Classes

Before this feature works, each MongoDB entry with IPA data needs a precomputed `phonetic` subdocument. See the companion file `lingpy_integration.py` for the precomputation script. The resulting document structure:

```json
{
  "word": "ignis",
  "lang": "Latin",
  "pos": "noun",
  "sounds": [{"ipa": "/ˈiɡ.nis/"}],
  "senses": [{"glosses": ["fire"]}],
  "phonetic": {
    "ipa": "ˈiɡnis",
    "dolgo_classes": "VKNVS",
    "dolgo_consonants": "KNS",
    "dolgo_first2": "KN",
    "tokens": ["i", "ɡ", "n", "i", "s"]
  }
}
```

### 3.2 Concept Resolution

The core challenge: given a concept like "fire", find all words across all languages that mean "fire". Three strategies, in order of reliability:

#### Strategy A: Wiktionary Translation Hubs (Primary)

Wiktionary entries often contain translation sections. In the kaikki.org dump, these appear as `translations` arrays on English entries. The structure typically looks like:

```json
{
  "word": "fire",
  "lang": "English",
  "translations": [
    {
      "sense": "uncountable: oxidation reaction",
      "lang": "Hungarian",
      "code": "hu",
      "word": "tűz"
    },
    {
      "sense": "uncountable: oxidation reaction",
      "lang": "Latin",
      "code": "la",
      "word": "ignis"
    }
  ]
}
```

**Implementation:**
1. Query the English entry for the concept word
2. Extract all translations from the relevant sense(s)
3. For each translation, look up the full entry in the database to get IPA/sound classes
4. This gives the cleanest, most reliable concept-to-word mapping

**MongoDB query sketch:**
```python
# Step 1: Get translations from English hub entry
hub = db.entries.find_one({
    "word": concept,
    "lang": "English",
    "translations": {"$exists": True}
}, {"translations": 1, "senses": 1})

# Step 2: Extract translation words
translation_pairs = [
    {"word": t["word"], "lang": t["lang"]}
    for t in hub.get("translations", [])
    if t.get("word") and t.get("lang")
]

# Step 3: Look up full entries with phonetic data
words = db.entries.find({
    "$or": translation_pairs,
    "phonetic.ipa": {"$ne": None}
})
```

#### Strategy B: Gloss Search (Fallback)

For concepts where the translation hub is incomplete, search across all entries whose glosses contain the concept term:

```python
db.entries.find({
    "senses.glosses": {"$regex": f"^{concept}$", "$options": "i"},
    "phonetic.ipa": {"$ne": None}
})
```

**Caution:** This is noisier. "fire" as a gloss could match "to fire someone" or "fireplace". Restrict to exact matches or use POS filtering (noun only for concrete concepts).

#### Strategy C: Concept Expansion (Optional Enhancement)

For richer results, allow related concepts. For "fire", also include words meaning "flame", "blaze", "burn". This could be:
- A hardcoded synonym map for common Swadesh concepts
- Wiktionary's own "related terms" / "synonyms" sections
- A future enhancement, not needed for v1

**Recommended approach for v1:** Use Strategy A (translation hubs) as primary, fall back to Strategy B (gloss search) when translations are sparse. Return which strategy was used so the frontend can indicate confidence.

### 3.3 Phonetic Similarity Matrix

Once we have all words for a concept, compute pairwise similarity. This is the data that drives the force-directed layout.

#### Similarity Computation

Use Dolgopolsky consonant class comparison. Two metrics:

**Metric 1: Consonant Class Levenshtein Distance (recommended)**

Compute the Levenshtein edit distance between the Dolgopolsky consonant class strings, normalized by the length of the longer string.

```python
def dolgopolsky_distance(cc1: str, cc2: str) -> float:
    """
    Normalized Levenshtein distance between consonant class strings.
    Returns 0.0 (identical) to 1.0 (completely different).
    """
    if not cc1 and not cc2:
        return 0.0
    if not cc1 or not cc2:
        return 1.0

    # Standard Levenshtein computation
    n, m = len(cc1), len(cc2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if cc1[i-1] == cc2[j-1] else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,      # deletion
                dp[i][j-1] + 1,      # insertion
                dp[i-1][j-1] + cost  # substitution
            )

    max_len = max(n, m)
    return dp[n][m] / max_len if max_len > 0 else 0.0
```

Similarity = 1.0 - distance.

**Metric 2: First-Two Match (for quick binary grouping)**

A boolean: do the first two consonant classes match? This is the classic Turchin/Dolgopolsky method. Useful for highlighting potential cognates vs. clearly unrelated forms.

#### Performance Note

For N words, pairwise comparison is O(N²). For typical concepts:
- Common Swadesh items might have 200-400 translations → 40K-160K pairs
- This is very fast with short string Levenshtein (microseconds per pair)
- Total computation: well under 1 second

For rare concepts with few translations, this is trivial. No optimization needed for v1.

### 3.4 Edge Filtering

Not all pairwise similarities should become edges in the graph. Too many edges = visual chaos.

**Rules:**
1. Only create edges where similarity > threshold (default: 0.6)
2. Always create edges where first-two consonant classes match (Turchin match), regardless of overall similarity
3. Optionally overlay known etymological edges from the existing etymology data (different visual style)
4. Allow the user to adjust the similarity threshold via a slider

---

## 4. API Design

### 4.1 `GET /api/concept-map`

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `concept` | string | yes | — | The concept to map (e.g., "fire", "water") |
| `pos` | string | no | any | Part of speech filter ("noun", "verb", etc.) |
| `similarity_threshold` | float | no | 0.6 | Min similarity for edges (0.0–1.0) |
| `max_words` | int | no | 200 | Max words to include |
| `include_etymology_edges` | bool | no | true | Overlay known etymological connections |

**Response:**

```json
{
  "concept": "fire",
  "resolution_method": "translation_hub",
  "words": [
    {
      "id": "fire_en",
      "word": "fire",
      "lang": "English",
      "lang_code": "en",
      "lang_family": "Germanic",
      "ipa": "faɪər",
      "dolgo_classes": "PVR",
      "dolgo_consonants": "PR",
      "pos": "noun",
      "has_etymology": true,
      "etymology_origin": "unknown"
    },
    {
      "id": "ignis_la",
      "word": "ignis",
      "lang": "Latin",
      "lang_code": "la",
      "lang_family": "Italic",
      "ipa": "ˈiɡnis",
      "dolgo_classes": "VKNVS",
      "dolgo_consonants": "KNS",
      "pos": "noun",
      "has_etymology": true,
      "etymology_origin": "PIE *h₁égnis"
    },
    {
      "id": "tűz_hu",
      "word": "tűz",
      "lang": "Hungarian",
      "lang_code": "hu",
      "lang_family": "Uralic",
      "ipa": "tyːz",
      "dolgo_classes": "TVS",
      "dolgo_consonants": "TS",
      "pos": "noun",
      "has_etymology": true,
      "etymology_origin": "Uralic"
    }
  ],
  "phonetic_edges": [
    {
      "source": "ignis_la",
      "target": "agni_sa",
      "similarity": 0.95,
      "turchin_match": true,
      "shared_classes": "KN"
    },
    {
      "source": "ég_hu",
      "target": "ignis_la",
      "similarity": 0.72,
      "turchin_match": true,
      "shared_classes": "K"
    }
  ],
  "etymology_edges": [
    {
      "source": "ignis_la",
      "target": "agni_sa",
      "relationship": "cognate",
      "proto_form": "*h₁égnis"
    },
    {
      "source": "fire_en",
      "target": "vuur_nl",
      "relationship": "cognate",
      "proto_form": "*péh₂wr̥"
    }
  ],
  "clusters": [
    {
      "id": "cluster_KN",
      "label": "K-N group",
      "words": ["ignis_la", "agni_sa", "ogni_ru", "ugnis_lt"],
      "note": "Potential PIE *h₁égnis reflexes"
    }
  ]
}
```

### 4.2 `GET /api/concepts/suggest`

Autocomplete endpoint for the concept search bar.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | yes | Partial concept name |
| `limit` | int | no | Max suggestions (default 10) |

**Response:**

```json
{
  "suggestions": [
    {"concept": "fire", "translation_count": 342, "has_hub": true},
    {"concept": "fireplace", "translation_count": 87, "has_hub": true},
    {"concept": "firewood", "translation_count": 45, "has_hub": true}
  ]
}
```

**Implementation:** Query English entries that have translation arrays, matching word prefix. Sort by translation count descending (more translations = richer concept map).

### 4.3 `GET /api/concept-map/word-detail`

When user clicks a node, fetch full details for the side panel.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `word` | string | yes | The word |
| `lang` | string | yes | The language |

**Response:**

```json
{
  "word": "ignis",
  "lang": "Latin",
  "ipa": "ˈiɡnis",
  "dolgo_classes": "VKNVS",
  "dolgo_consonants": "KNS",
  "pos": "noun",
  "senses": [
    {"gloss": "fire", "tags": []},
    {"gloss": "brightness, shine", "tags": ["figurative"]}
  ],
  "etymology_text": "From Proto-Italic *eignis, from PIE *h₁égnis...",
  "etymology_links": [
    {"word": "*eignis", "lang": "Proto-Italic", "relation": "from"},
    {"word": "*h₁égnis", "lang": "Proto-Indo-European", "relation": "from"}
  ],
  "descendants": [
    {"word": "ignite", "lang": "English"},
    {"word": "ignição", "lang": "Portuguese"}
  ]
}
```

---

## 5. Frontend Specification

### 5.1 Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ [Etymology Explorer]   [Etymology View]  [★ Concept Map]        │
├──────────────────────────────────────────────────────────────────┤
│                                                    │             │
│  ┌─────────────────────────────────┐               │  DETAIL     │
│  │ Search: [fire________] [Go]     │               │  PANEL      │
│  │ Filter: ○ All  ○ Nouns  ○ Verbs │               │             │
│  └─────────────────────────────────┘               │  (appears   │
│                                                    │   on node   │
│            ┌──────────────────────┐                │   click)    │
│            │                      │                │             │
│            │   Force-directed     │                │  Word: ...  │
│            │   concept map        │                │  Lang: ...  │
│            │                      │                │  IPA: ...   │
│            │    (vis.js canvas)   │                │  Classes:.. │
│            │                      │                │  Etym: ...  │
│            │                      │                │             │
│            └──────────────────────┘                │  [View in   │
│                                                    │  Etymology  │
│  ┌──────────────────────────────────────────┐      │   Graph →]  │
│  │ Similarity: [====●=====] 0.60            │      │             │
│  │ ☑ Show etymology edges                   │      │             │
│  │ ☑ Color by language family                │      │             │
│  │ ○ Color by consonant class cluster        │      │             │
│  │ Legend: ── phonetic  ━━ etymological      │      │             │
│  └──────────────────────────────────────────┘      │             │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Node Design

Each node represents one word in one language.

**Node content:**
- Label: `word` (primary, large text)
- Sublabel: `(language)` (secondary, smaller text)

**Node color: by language family** (default, matches existing Etymology Explorer palette)

| Family | Color | Example |
|--------|-------|---------|
| Germanic | Blue `#4A90D9` | fire, Feuer, vuur |
| Romance | Red `#D94A4A` | fuoco, feu, fuego |
| Slavic | Green `#4AD94A` | огонь, oheň |
| Indo-Iranian | Orange `#D9A04A` | agni, آتش |
| Uralic | Yellow `#D9D94A` | tűz, tuli |
| Celtic | Purple `#9B59B6` | tine, tân |
| PIE (reconstructed) | Gold `#F1C40F` | *h₁égnis, *péh₂wr̥ |
| Other | Grey `#95A5A6` | — |

Reuse existing color scheme from the Etymology Explorer's language family legend.

**Node shape:**
- Standard: rounded rectangle (box)
- Words marked "unknown origin" in their etymology: **double border** or **highlighted ring** — these are the interesting ones

**Node size:** Uniform. Don't vary by frequency or importance — keep it neutral.

### 5.3 Edge Design

Two types of edges, visually distinct:

**Phonetic similarity edges:**
- Style: dashed line `- - - -`
- Color: grey, with opacity proportional to similarity score
- Width: 1-3px scaled by similarity
- Label: similarity percentage (e.g., `87%`), shown on hover only to reduce clutter
- These are the primary structural edges that drive the force layout

**Etymological edges** (optional overlay):
- Style: solid line `────`
- Color: dark, semi-transparent
- Width: 2px
- Label: relationship type (e.g., "cognate", "borrowed"), shown on hover
- Arrow direction: from ancestor to descendant (if applicable)
- These do NOT affect the force layout — they're purely visual overlay

### 5.4 Force Layout Configuration

The force-directed graph should use **phonetic similarity as attractive force**. Words that sound similar pull together; words that sound different drift apart.

**vis.js physics configuration:**

```javascript
const options = {
  physics: {
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {
      gravitationalConstant: -30,
      centralGravity: 0.005,
      springLength: 150,
      springConstant: 0.08,
      damping: 0.4,
      avoidOverlap: 0.5
    },
    stabilization: {
      iterations: 300,
      updateInterval: 25
    }
  },
  edges: {
    smooth: {
      type: 'continuous'
    }
  }
};
```

**Edge length mapping:**
- Similarity 1.0 → spring length 50 (very close)
- Similarity 0.6 → spring length 200 (moderately close)
- Below threshold → no edge (nodes drift to periphery)

```javascript
// Map similarity to edge length (inverse relationship)
function similarityToEdgeLength(similarity) {
  const minLength = 50;
  const maxLength = 250;
  return maxLength - (similarity * (maxLength - minLength));
}
```

### 5.5 Interaction

**Search & Load:**
1. User types concept in search bar
2. Autocomplete suggests concepts (from `/api/concepts/suggest`)
3. User selects or presses Enter
4. Loading indicator while API computes
5. Graph animates into position

**Node Click:**
1. Node highlights (border glow)
2. All edges connected to this node become opaque, others fade
3. Detail panel opens on the right showing word info, etymology, IPA breakdown
4. "View in Etymology Graph →" button navigates to the Etymology Explorer for that word

**Node Hover:**
- Tooltip shows: word, language, IPA, Dolgopolsky classes
- Connected edges show their similarity labels

**Controls:**

| Control | Type | Effect |
|---------|------|--------|
| Similarity threshold | Range slider (0.0–1.0) | Adds/removes phonetic edges. Graph re-stabilizes. |
| Show etymology edges | Checkbox | Toggles etymological edge overlay |
| Color mode | Radio buttons | "By language family" / "By consonant cluster" |
| POS filter | Radio buttons | All / Nouns / Verbs / Adjectives |
| Highlight unknown origins | Checkbox | Adds visual emphasis to words with unknown/debated etymology |

**"Highlight unknown origins" behavior:**
When enabled, words whose `etymology_origin` contains "unknown", "uncertain", or "disputed" get a pulsing golden ring. This is a subtle research affordance — it draws the eye to exactly the words where current etymology fails to explain the form, while they may be sitting right next to phonetically similar words in well-established etymological chains.

### 5.6 Cluster Visualization (Optional Enhancement)

If the API returns `clusters` (groups of words sharing the same first-two consonant classes), display them as a **faint convex hull or background region** behind the clustered nodes.

Label each cluster with its consonant class pattern (e.g., "K-N group", "P-R group").

This makes it immediately visible that, say, Latin *ignis*, Sanskrit *agni*, Lithuanian *ugnis*, and Russian *огонь* all cluster together in the K-N group, while English *fire*, Dutch *vuur*, and German *Feuer* cluster in the P-R group.

---

## 6. Backend Implementation Details

### 6.1 Concept Resolution Function

```python
def resolve_concept(concept: str, db, pos: str = None, max_words: int = 200) -> list[dict]:
    """
    Find all words across languages that express the given concept.
    Returns list of word entries with phonetic data.
    """
    results = []
    method = None

    # Strategy A: Translation hub
    hub_query = {
        "word": concept,
        "lang": "English",
        "translations": {"$exists": True, "$ne": []}
    }
    hub = db.entries.find_one(hub_query)

    if hub and hub.get("translations"):
        method = "translation_hub"

        # Collect unique (word, lang) pairs from translations
        seen = set()
        lookup_pairs = []

        for t in hub["translations"]:
            key = (t.get("word", ""), t.get("lang", ""))
            if key[0] and key[1] and key not in seen:
                seen.add(key)
                lookup_pairs.append({"word": key[0], "lang": key[1]})

        # Also add the English word itself
        lookup_pairs.append({"word": concept, "lang": "English"})

        # Batch lookup
        if lookup_pairs:
            query = {
                "$or": lookup_pairs,
                "phonetic.ipa": {"$ne": None}
            }
            if pos:
                query["pos"] = pos

            results = list(db.entries.find(query).limit(max_words))

    # Strategy B: Gloss search fallback
    if len(results) < 10:
        method = method or "gloss_search"
        gloss_query = {
            "senses.glosses": {"$regex": f"^{re.escape(concept)}$", "$options": "i"},
            "phonetic.ipa": {"$ne": None}
        }
        if pos:
            gloss_query["pos"] = pos

        existing_keys = {(r["word"], r["lang"]) for r in results}

        for doc in db.entries.find(gloss_query).limit(max_words - len(results)):
            key = (doc["word"], doc["lang"])
            if key not in existing_keys:
                results.append(doc)
                existing_keys.add(key)

    return results, method
```

### 6.2 Similarity Matrix Function

```python
def build_similarity_matrix(
    words: list[dict],
    threshold: float = 0.6
) -> list[dict]:
    """
    Compute pairwise phonetic similarity for all words.
    Returns list of edges above threshold.
    """
    edges = []

    for i in range(len(words)):
        cc_i = words[i].get("phonetic", {}).get("dolgo_consonants", "")
        f2_i = words[i].get("phonetic", {}).get("dolgo_first2", "")

        for j in range(i + 1, len(words)):
            cc_j = words[j].get("phonetic", {}).get("dolgo_consonants", "")
            f2_j = words[j].get("phonetic", {}).get("dolgo_first2", "")

            # Skip if either has no consonant data
            if not cc_i or not cc_j:
                continue

            sim = 1.0 - dolgopolsky_distance(cc_i, cc_j)
            turchin = (
                len(f2_i) >= 2 and len(f2_j) >= 2 and f2_i == f2_j
            )

            # Include if above threshold OR if Turchin match
            if sim >= threshold or turchin:
                id_i = f"{words[i]['word']}_{words[i].get('lang_code', words[i]['lang'][:2].lower())}"
                id_j = f"{words[j]['word']}_{words[j].get('lang_code', words[j]['lang'][:2].lower())}"

                edges.append({
                    "source": id_i,
                    "target": id_j,
                    "similarity": round(sim, 3),
                    "turchin_match": turchin,
                    "shared_classes": _shared_prefix(cc_i, cc_j)
                })

    return edges


def _shared_prefix(cc1: str, cc2: str) -> str:
    """Return the longest shared prefix of two consonant class strings."""
    prefix = []
    for a, b in zip(cc1, cc2):
        if a == b:
            prefix.append(a)
        else:
            break
    return "".join(prefix)
```

### 6.3 Etymology Edge Extraction

```python
def extract_etymology_edges(words: list[dict], db) -> list[dict]:
    """
    For the set of words on the concept map, find any known
    etymological connections between them.

    Checks the etymology_templates and descendants fields
    in the Wiktionary data.
    """
    edges = []
    word_set = {(w["word"], w["lang"]) for w in words}

    for w in words:
        # Check etymology_templates for "from" relationships
        for tmpl in w.get("etymology_templates", []):
            if tmpl.get("name") in ("inh", "bor", "der", "cog"):
                target_word = tmpl.get("args", {}).get("2", "")
                target_lang = tmpl.get("expansion", "")
                # Try to match against words in our set
                # (This requires language code → name mapping)
                pass

        # Check descendants
        for desc in w.get("descendants", []):
            desc_key = (desc.get("word", ""), desc.get("lang", ""))
            if desc_key in word_set:
                edges.append({
                    "source": _make_id(w),
                    "target": _make_id_from_tuple(desc_key),
                    "relationship": "parent→descendant"
                })

    return edges
```

**Note to implementer:** The etymology edge extraction from Wiktionary's template data is messy. The `etymology_templates` structure varies. A pragmatic v1 approach: for each word pair in the concept map, check if word A appears anywhere in word B's `etymology_text` (raw text search). This catches most connections with minimal parsing.

### 6.4 Language Family Mapping

You'll need a language → family mapping for node coloring. The kaikki.org dump may include this, but if not, a reasonable starting point:

```python
# Simplified mapping — extend as needed
LANG_FAMILIES = {
    "Germanic": ["English", "German", "Dutch", "Swedish", "Norwegian",
                  "Danish", "Icelandic", "Afrikaans", "Yiddish",
                  "Old English", "Old Norse", "Gothic",
                  "Proto-Germanic", "Proto-West Germanic"],
    "Romance": ["French", "Spanish", "Italian", "Portuguese", "Romanian",
                "Catalan", "Occitan", "Galician", "Sardinian",
                "Old French", "Latin", "Proto-Italic", "Vulgar Latin"],
    "Slavic": ["Russian", "Polish", "Czech", "Slovak", "Ukrainian",
               "Bulgarian", "Serbian", "Croatian", "Slovenian",
               "Old Church Slavonic", "Proto-Slavic"],
    "Indo-Iranian": ["Sanskrit", "Hindi", "Urdu", "Persian", "Bengali",
                     "Pashto", "Kurdish", "Avestan", "Old Persian",
                     "Proto-Indo-Iranian"],
    "Celtic": ["Irish", "Welsh", "Scottish Gaelic", "Breton", "Cornish",
               "Old Irish", "Proto-Celtic"],
    "Baltic": ["Lithuanian", "Latvian", "Old Prussian", "Proto-Baltic"],
    "Hellenic": ["Greek", "Ancient Greek", "Proto-Hellenic"],
    "Uralic": ["Hungarian", "Finnish", "Estonian", "Sami",
               "Proto-Uralic", "Proto-Finno-Ugric"],
    "Turkic": ["Turkish", "Azerbaijani", "Kazakh", "Uzbek",
               "Proto-Turkic"],
    "PIE": ["Proto-Indo-European"],
}

def get_lang_family(lang: str) -> str:
    for family, langs in LANG_FAMILIES.items():
        if lang in langs:
            return family
    return "Other"
```

**Better approach:** Wiktionary entries include a `lang_code` field. Use Glottolog or Wiktionary's own language metadata to map codes to families programmatically. But the hardcoded map above works for v1.

---

## 7. Test Cases

### 7.1 "fire" (Classic Test)

Expected clusters:
- **K-N group**: Latin *ignis*, Sanskrit *agni*, Lithuanian *ugnis*, Old Church Slavonic *огнь*, possibly Hungarian *ég* (verb "to burn")
- **P-R group**: English *fire*, German *Feuer*, Dutch *vuur*, Greek *πῦρ* (from PIE \*péh₂wr̥)
- **T-group**: Hungarian *tűz*, Finnish *tuli* (Uralic)
- **Isolates**: Turkish *ateş* (Persian loan), Japanese *火* (hi), Chinese *火* (huǒ)

This concept should show clear phonetic clustering that partly overlaps with but is not identical to etymological grouping. Hungarian *ég* clustering with the ignis/agni group despite being classified as Uralic would be visually striking.

### 7.2 "water" (High Coverage)

Expected clusters:
- **W-T group**: English *water*, German *Wasser*, Russian *вода* (all from PIE \*wódr̥)
- **V-S group**: Hungarian *víz*, Finnish *vesi* (Uralic)
- **Interesting**: Hungarian *víz* and PIE \*wódr̥ reflexes share the initial V/W class

### 7.3 "circle" (Tests Your Research Area)

Expected to surface: Hungarian *kör*, Latin *circus*, Greek *κίρκος*, possible other K-R pattern words.

### 7.4 Edge Cases

- **Concept with no translation hub**: Try a less common concept to verify gloss fallback works
- **Concept with thousands of translations**: Verify `max_words` limit prevents overload
- **Single-phoneme words**: Short words with 0-1 consonants produce degenerate similarity scores; handle gracefully

---

## 8. Implementation Priorities

### Phase 1 (Core — get it working)

1. Precompute Dolgopolsky classes for all IPA entries (run `lingpy_integration.py`)
2. Implement `/api/concept-map` endpoint with translation hub resolution
3. Implement basic vis.js concept map with phonetic similarity edges
4. Node coloring by language family
5. Basic detail panel on click

### Phase 2 (Usability)

6. Similarity threshold slider (dynamic edge filtering, client-side)
7. Concept search autocomplete
8. POS filter
9. Etymology edge overlay (checkbox toggle)
10. "View in Etymology Graph" link from detail panel

### Phase 3 (Research Features)

11. "Highlight unknown origins" toggle
12. Cluster convex hulls
13. Export data as CSV/JSON for further analysis
14. Multiple concept comparison (side by side or overlaid)

---

## 9. Important Notes for Implementer

**On neutrality:** This tool must feel like a neutral instrument. It shows ALL words for a concept and lets the phonetic similarity algorithm place them. It does not pre-select which connections to highlight. The "unknown origin" highlight is the one editorial choice, and it should be opt-in (checkbox off by default).

**On the existing codebase:** This is a new view within the existing Etymology Explorer. It should share the same MongoDB connection, the same language family color scheme, and ideally the same vis.js setup. The concept map is a sibling to the etymology graph, not a replacement.

**On LingPy dependency:** LingPy is only needed for the precomputation step (converting IPA to Dolgopolsky classes). Once the `phonetic` subdocuments are in MongoDB, the runtime code (API, similarity computation) has zero LingPy dependency — it's all string comparison. This keeps the deployed backend lightweight.

**On the Wiktionary data structure:** The kaikki.org dump format can vary slightly between dumps. The implementer should verify the exact field names for `translations`, `senses`, `etymology_templates`, and `sounds` against the actual data in MongoDB. The field names used in this spec are based on the standard kaikki.org schema but should be confirmed.
