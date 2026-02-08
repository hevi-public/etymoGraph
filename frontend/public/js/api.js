const API_BASE = "/api";

async function searchWords(query) {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&limit=20`);
    if (!res.ok) throw new Error(`Search failed (${res.status})`);
    return res.json();
}

async function getWord(word, lang = "English") {
    const res = await fetch(`${API_BASE}/words/${encodeURIComponent(word)}?lang=${encodeURIComponent(lang)}`);
    if (!res.ok) throw new Error(`Word not found (${res.status})`);
    return res.json();
}

async function getEtymologyChain(word, lang = "English") {
    const res = await fetch(`${API_BASE}/etymology/${encodeURIComponent(word)}/chain?lang=${encodeURIComponent(lang)}`);
    if (!res.ok) throw new Error(`Etymology chain failed (${res.status})`);
    return res.json();
}

async function getEtymologyTree(word, lang = "English", types = "inh") {
    const res = await fetch(`${API_BASE}/etymology/${encodeURIComponent(word)}/tree?lang=${encodeURIComponent(lang)}&types=${encodeURIComponent(types)}`);
    if (!res.ok) throw new Error(`Etymology tree failed (${res.status})`);
    return res.json();
}

async function getConceptMap(concept, pos = null, maxWords = 200) {
    let url = `${API_BASE}/concept-map?concept=${encodeURIComponent(concept)}&max_words=${maxWords}`;
    if (pos) url += `&pos=${encodeURIComponent(pos)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Concept map failed (${res.status})`);
    return res.json();
}

async function getConceptSuggestions(query) {
    const res = await fetch(`${API_BASE}/concepts/suggest?q=${encodeURIComponent(query)}&limit=10`);
    if (!res.ok) throw new Error(`Concept suggestions failed (${res.status})`);
    return res.json();
}
