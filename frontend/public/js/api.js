const API_BASE = "/api";

async function searchWords(query) {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&limit=20`);
    if (!res.ok) throw new Error("Search failed");
    return res.json();
}

async function getWord(word, lang = "English") {
    const res = await fetch(`${API_BASE}/words/${encodeURIComponent(word)}?lang=${encodeURIComponent(lang)}`);
    if (!res.ok) throw new Error("Word not found");
    return res.json();
}

async function getEtymologyChain(word, lang = "English") {
    const res = await fetch(`${API_BASE}/etymology/${encodeURIComponent(word)}/chain?lang=${encodeURIComponent(lang)}`);
    if (!res.ok) throw new Error("Etymology chain failed");
    return res.json();
}

async function getEtymologyTree(word, lang = "English", types = "inh") {
    const res = await fetch(`${API_BASE}/etymology/${encodeURIComponent(word)}/tree?lang=${encodeURIComponent(lang)}&types=${encodeURIComponent(types)}`);
    if (!res.ok) throw new Error("Etymology tree failed");
    return res.json();
}
