const graphContainer = document.getElementById("graph");

function formatEtymologyText(text, templates) {
    if (!text) return '<span class="etym-empty">No etymology text available.</span>';

    // Escape HTML
    const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    // Build lookup from templates: word → {word, lang_code} for linkable terms
    // Kaikki templates have args as dict with string keys: "1"=source_lang, "2"=target_lang, "3"=word
    // For cognates: "1"=lang_code, "2"=word
    const templateLookup = {};
    if (templates && templates.length) {
        // Process cognates first, then ancestry types so ancestry takes priority for shared words
        for (const t of templates) {
            if (!t.args || t.name !== "cog") continue;
            const langCode = t.args["1"] || "";
            const w = t.args["2"] || "";
            if (w && langCode) templateLookup[w] = { word: w, lang_code: langCode };
        }
        for (const t of templates) {
            if (!t.args) continue;
            if (!["inh", "bor", "der"].includes(t.name)) continue;
            const langCode = t.args["2"] || "";
            const w = t.args["3"] || "";
            if (w && langCode) templateLookup[w] = { word: w, lang_code: langCode };
        }
    }

    // Create a link for a word if it exists in the template lookup
    function makeLink(displayText, word) {
        const entry = templateLookup[word] || templateLookup[word.replace(/^\*/, "")];
        if (!entry) return esc(displayText);
        return `<a class="etym-link" href="#" data-word="${esc(entry.word)}" data-lang-code="${esc(entry.lang_code)}">${esc(displayText)}</a>`;
    }

    // Try to linkify text by matching known template words
    function linkifyText(escaped) {
        if (!Object.keys(templateLookup).length) return escaped;
        // Sort by length descending to match longer words first
        const words = Object.keys(templateLookup).sort((a, b) => b.length - a.length);
        const pattern = new RegExp("(?<![\\w*])(" + words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join("|") + ")(?!\\w)", "g");
        return escaped.replace(pattern, (match) => {
            const entry = templateLookup[match];
            if (!entry) return match;
            return `<a class="etym-link" href="#" data-word="${esc(entry.word)}" data-lang-code="${esc(entry.lang_code)}">${match}</a>`;
        });
    }

    // Split into sections: etymology tree, main prose, cognates
    let tree = "";
    let prose = "";
    let cognates = "";

    const lines = text.split("\n");
    let section = "auto"; // auto-detect

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed === "Etymology tree") {
            section = "tree";
            continue;
        }
        if (trimmed === "Cognates" || trimmed === "Cognates:") {
            section = "cognates";
            continue;
        }
        // Prose typically starts with "From " or "Borrowed " etc.
        if (section === "tree" && /^(From |Borrowed |Learned |Coined |Back-formation|A |The |Inherited |Uncertain|Originally|Perhaps|Probably|Possibly|Compare |Cf\.|Related |See |Also |Equivalent |Compound |Blend |Variant |Alteration |Clipping |Abbreviation |Acronym |Named )/.test(trimmed)) {
            section = "prose";
        }

        if (section === "tree") {
            tree += (tree ? "\n" : "") + trimmed;
        } else if (section === "cognates") {
            cognates += (cognates ? "\n" : "") + trimmed;
        } else {
            // prose or auto
            prose += (prose ? "\n" : "") + trimmed;
            section = "prose";
        }
    }

    let html = "";

    // Render etymology tree as a chain with arrows
    if (tree) {
        const steps = tree.split("\n").map(s => {
            // Chain items are "Language word" (e.g. "Old English wæter") or "word (Language)"
            const parenMatch = s.match(/^(\*?\S+)\s*\((.+)\)$/);
            if (parenMatch) {
                return makeLink(parenMatch[1], parenMatch[1]) + " (" + esc(parenMatch[2]) + ")";
            }
            // Try "Language word" format: extract last token as the word
            const lastSpace = s.lastIndexOf(" ");
            if (lastSpace > 0) {
                const word = s.slice(lastSpace + 1);
                const lang = s.slice(0, lastSpace);
                const entry = templateLookup[word] || templateLookup[word.replace(/^\*/, "")];
                if (entry) {
                    return esc(lang) + " " + makeLink(word, word);
                }
            }
            return esc(s);
        });
        html += '<div class="etym-chain">' + steps.join(' <span class="etym-arrow">→</span> ') + "</div>";
    }

    // Render prose: highlight foreign terms in parentheses like φίλος (phílos, "loving")
    if (prose) {
        let escaped = esc(prose);
        // Bold language names at start of sentences like "From Middle English", "from Proto-Germanic"
        escaped = escaped.replace(/\b(from|From|of)\s+((?:Proto-|Middle |Old |Late |Ancient |Medieval |Vulgar |Biblical |Classical )*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g,
            '$1 <strong>$2</strong>');
        // Style quoted terms: ("word") or ("word", "gloss")
        escaped = escaped.replace(/\(("[^"]*")\)/g, '<span class="etym-gloss">($1)</span>');
        // Linkify known template words in prose
        escaped = linkifyText(escaped);
        html += '<p class="etym-prose">' + escaped + "</p>";
    }

    // Render cognates as a compact list
    if (cognates) {
        const items = cognates.split("\n").map((c) => c.replace(/^\*\s*/, "").trim()).filter(Boolean);
        html += '<details class="etym-cognates"><summary>Cognates (' + items.length + ")</summary><p>";
        html += items.map(c => {
            // Cognates are "Language word ("gloss")" e.g. 'Scots watter ("water")'
            // Extract the word before the gloss parenthetical
            const glossMatch = c.match(/^(.+?)\s+(\(".+"\))$/);
            if (glossMatch) {
                const before = glossMatch[1]; // "Scots watter"
                const gloss = glossMatch[2];  // ("water")
                // Last token of before is the word
                const ls = before.lastIndexOf(" ");
                if (ls > 0) {
                    const word = before.slice(ls + 1);
                    const lang = before.slice(0, ls);
                    return esc(lang) + " " + makeLink(word, word) + " " + '<span class="etym-gloss">' + esc(gloss) + "</span>";
                }
                return makeLink(before, before) + " " + '<span class="etym-gloss">' + esc(gloss) + "</span>";
            }
            // Fallback: try linkifying the whole thing
            return linkifyText(esc(c));
        }).join(", ");
        html += "</p></details>";
    }

    return html || '<span class="etym-empty">No etymology text available.</span>';
}

const LANG_COLORS = {
    germanic: "#5B8DEF",
    romance: "#EF5B5B",
    greek: "#43D9A2",
    pie: "#F5C842",
    slavic: "#CE6BF0",
    celtic: "#FF8C42",
    indoiranian: "#FF6B9D",
    semitic: "#00BCD4",
    uralic: "#8BC34A",
    other: "#A0A0B8",
};

function langColor(lang) {
    if (/english|german|norse|dutch|frisian|gothic|proto-germanic|proto-west germanic|saxon|scots|yiddish|afrikaans|plautdietsch|limburgish|luxembourgish|cimbrian|alemannic|bavarian|vilamovian|saterland/i.test(lang)) return LANG_COLORS.germanic;
    if (/latin|italic|french|spanish|portuguese|romanian|proto-italic|catalan|occitan|sardinian|galician|venetian|sicilian|neapolitan|asturian/i.test(lang)) return LANG_COLORS.romance;
    if (/greek/i.test(lang)) return LANG_COLORS.greek;
    if (/proto-indo-european/i.test(lang)) return LANG_COLORS.pie;
    if (/russian|polish|czech|slovak|serbian|croatian|bulgarian|ukrainian|slovene|proto-slavic|old church slavonic|belarusian|macedonian|sorbian/i.test(lang)) return LANG_COLORS.slavic;
    if (/irish|welsh|scottish gaelic|breton|cornish|manx|proto-celtic|old irish/i.test(lang)) return LANG_COLORS.celtic;
    if (/sanskrit|hindi|persian|urdu|bengali|punjabi|avestan|pali|proto-indo-iranian/i.test(lang)) return LANG_COLORS.indoiranian;
    if (/arabic|hebrew|aramaic|akkadian|proto-semitic/i.test(lang)) return LANG_COLORS.semitic;
    if (/finnish|hungarian|estonian|proto-uralic|proto-finnic/i.test(lang)) return LANG_COLORS.uralic;
    return LANG_COLORS.other;
}

const EDGE_LABELS = { inh: "inherited", bor: "borrowed", der: "derived", cog: "cognate" };

const OPACITY_BY_HOP = [1.0, 0.9, 0.5, 0.1]; // 0 hops, 1 hop, 2 hops, 3+ hops

function colorWithOpacity(hex, opacity) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${opacity})`;
}

function opacityForHops(hops) {
    if (hops >= OPACITY_BY_HOP.length) return OPACITY_BY_HOP[OPACITY_BY_HOP.length - 1];
    return OPACITY_BY_HOP[hops];
}

const graphOptions = {
    layout: {
        improvedLayout: true,
    },
    edges: {
        color: { color: "#555", highlight: "#aaa" },
        font: { color: "#999", size: 11, strokeWidth: 0 },
        smooth: { type: "continuous" },
        length: 200,
    },
    nodes: {
        shape: "box",
        borderWidth: 0,
        font: { size: 13, multi: true, color: "#fff" },
        margin: 10,
    },
    physics: {
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
            gravitationalConstant: -80,
            centralGravity: 0.01,
            springLength: 150,
            springConstant: 0.02,
            damping: 0.4,
        },
        stabilization: false,
    },
    interaction: {
        zoomView: false,
        dragView: true,
        hover: true,
    },
};

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let currentNodes = [];
let nodeBaseColors = {};  // id → hex color
let rootNodeId = null;   // etymological root (deepest ancestor)
let wordNodeId = null;   // searched word

function updateGraph(data) {
    if (network) {
        network.destroy();
    }
    currentNodes = data.nodes;

    // The searched word has level 0
    const wordNode = data.nodes.find((n) => n.level === 0);
    wordNodeId = wordNode ? wordNode.id : null;

    // The etymological root is the node with the lowest (most negative) level
    const etymRoot = data.nodes.reduce((min, n) => (n.level < min.level ? n : min), data.nodes[0]);
    rootNodeId = etymRoot ? etymRoot.id : null;

    nodeBaseColors = {};
    nodesDataSet = new vis.DataSet(
        data.nodes.map((n) => {
            const isRoot = n.id === rootNodeId;
            const color = langColor(n.language);
            nodeBaseColors[n.id] = color;
            return {
                ...n,
                label: `${n.label}\n(${n.language})`,
                color,
                // Pin the root node to the center
                mass: isRoot ? 5 : Math.max(1, 5 / Math.pow(2, Math.abs(n.level))),
                ...(isRoot ? { x: 0, y: 0, fixed: { x: true, y: true } } : {}),
            };
        })
    );
    const nodes = nodesDataSet;
    edgesDataSet = new vis.DataSet(
        data.edges.map((e) => ({
            ...e,
            label: EDGE_LABELS[e.label] || e.label,
            arrows: "to",
            dashes: e.label === "bor" || e.label === "cog",
            color: e.label === "cog" ? { color: "#F5C842", highlight: "#FFE066" } : undefined,
        }))
    );
    const edges = edgesDataSet;
    network = new vis.Network(graphContainer, { nodes, edges }, graphOptions);

    // Start view centered on the root node
    network.moveTo({ position: { x: 0, y: 0 }, scale: 1, animation: false });

    // Trackpad: pinch zooms (ctrlKey), two-finger scroll pans
    graphContainer.addEventListener("wheel", (e) => {
        e.preventDefault();
        if (e.ctrlKey) {
            // Pinch gesture — macOS sets ctrlKey for pinch
            const scale = network.getScale();
            const newScale = scale * (1 - e.deltaY * 0.01);
            network.moveTo({ scale: Math.max(0.1, Math.min(5, newScale)), animation: false });
        } else {
            // Two-finger scroll — pan, scaled by zoom level
            const pos = network.getViewPosition();
            const scale = network.getScale();
            network.moveTo({
                position: { x: pos.x + e.deltaX / scale, y: pos.y + e.deltaY / scale },
                animation: false,
            });
        }
    }, { passive: false });

    network.on("click", (params) => {
        if (params.nodes.length > 0) {
            const clickedId = params.nodes[0];
            const node = currentNodes.find((n) => n.id === clickedId);
            if (node) {
                showDetail(node.label, node.language);
            }
            applyBrightnessFromNode(clickedId, edges);
            const pos = network.getPositions([clickedId])[clickedId];
            if (pos) {
                network.moveTo({
                    position: { x: pos.x, y: pos.y },
                    animation: { duration: 400, easingFunction: "easeInOutQuad" },
                });
            }
        } else {
            // Clicked on empty space — reset all nodes to full brightness
            resetBrightness();
        }
    });
}

function selectNodeById(nodeId) {
    if (!network) return;
    network.selectNodes([nodeId]);
    const pos = network.getPositions([nodeId])[nodeId];
    if (pos) {
        network.moveTo({
            position: { x: pos.x, y: pos.y },
            animation: { duration: 400, easingFunction: "easeInOutQuad" },
        });
    }
    applyBrightnessFromNode(nodeId, edgesDataSet);
    const node = currentNodes.find((n) => n.id === nodeId);
    if (node) showDetail(node.label, node.language);
}

function buildConnectionsPanel(nodeId) {
    const container = document.getElementById("detail-connections");
    container.innerHTML = "";

    if (!edgesDataSet) return;

    const CONNECTION_SECTIONS = {
        inh: "Inherited",
        bor: "Borrowed",
        der: "Derived",
        cog: "Cognate",
    };

    // Collect edges from/to this node, grouped by original label
    const grouped = {};
    edgesDataSet.forEach((e) => {
        // e.label is the display label ("inherited"), we need the raw type
        const rawType = Object.keys(EDGE_LABELS).find((k) => EDGE_LABELS[k] === e.label) || e.label;
        let targetId = null;
        if (e.from === nodeId) targetId = e.to;
        else if (e.to === nodeId) targetId = e.from;
        if (!targetId) return;

        if (!grouped[rawType]) grouped[rawType] = [];
        grouped[rawType].push(targetId);
    });

    for (const [type, label] of Object.entries(CONNECTION_SECTIONS)) {
        const targets = grouped[type];
        if (!targets || targets.length === 0) continue;

        const h3 = document.createElement("h3");
        h3.textContent = label;
        container.appendChild(h3);

        const ul = document.createElement("ul");
        ul.className = "connection-list";
        for (const tid of targets) {
            const node = currentNodes.find((n) => n.id === tid);
            if (!node) continue;
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = "#";
            a.textContent = `${node.label} (${node.language})`;
            a.addEventListener("click", (ev) => {
                ev.preventDefault();
                selectNodeById(tid);
            });
            li.appendChild(a);
            ul.appendChild(li);
        }
        container.appendChild(ul);
    }
}

async function showDetail(word, lang) {
    const panel = document.getElementById("detail-panel");
    const wordEl = document.getElementById("detail-word");
    const langEl = document.getElementById("detail-lang");
    const posEl = document.getElementById("detail-pos");
    const ipaEl = document.getElementById("detail-ipa");
    const defsEl = document.getElementById("detail-defs");
    const etymEl = document.getElementById("detail-etym");

    wordEl.textContent = word;
    const wiktLink = document.getElementById("detail-wikt");
    if (lang.startsWith("Proto-")) {
        // e.g. Reconstruction:Proto-Italic/wīnom
        const cleanWord = word.replace(/^\*/, "");
        wiktLink.href = `https://en.wiktionary.org/wiki/Reconstruction:${encodeURIComponent(lang)}/${encodeURIComponent(cleanWord)}`;
    } else {
        wiktLink.href = `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}#${encodeURIComponent(lang)}`;
    }
    langEl.textContent = lang;
    posEl.textContent = "";
    ipaEl.textContent = "";
    defsEl.innerHTML = "";
    etymEl.textContent = "";
    panel.hidden = false;

    // Build connections from graph edges
    const nodeId = `${word}:${lang}`;
    buildConnectionsPanel(nodeId);

    try {
        const data = await getWord(word, lang);
        posEl.textContent = data.pos || "";
        ipaEl.textContent = data.pronunciation || "";
        defsEl.innerHTML = "";
        (data.definitions || []).forEach((d) => {
            const li = document.createElement("li");
            li.textContent = d;
            defsEl.appendChild(li);
        });
        etymEl.innerHTML = formatEtymologyText(data.etymology_text, data.etymology_templates);
    } catch (e) {
        const errSpan = document.createElement("span");
        errSpan.className = "etym-empty";
        errSpan.textContent = `Not in database (${lang} words are not in the English-only Kaikki dump).`;
        etymEl.innerHTML = "";
        etymEl.appendChild(errSpan);
    }
}

function applyBrightnessFromNode(startId, edgesDataSet) {
    // BFS to compute hop distance from the selected node
    const adjacency = {};
    edgesDataSet.forEach((e) => {
        if (!adjacency[e.from]) adjacency[e.from] = [];
        if (!adjacency[e.to]) adjacency[e.to] = [];
        adjacency[e.from].push(e.to);
        adjacency[e.to].push(e.from);
    });

    const dist = {};
    const queue = [startId];
    dist[startId] = 0;
    while (queue.length > 0) {
        const cur = queue.shift();
        for (const neighbor of adjacency[cur] || []) {
            if (!(neighbor in dist)) {
                dist[neighbor] = dist[cur] + 1;
                queue.push(neighbor);
            }
        }
    }

    const updates = [];
    for (const id in nodeBaseColors) {
        const hops = dist[id] ?? Infinity;
        const opacity = hops === Infinity ? OPACITY_BY_HOP[OPACITY_BY_HOP.length - 1] : opacityForHops(hops);
        const rgba = colorWithOpacity(nodeBaseColors[id], opacity);
        const fontOpacity = opacity;
        updates.push({
            id,
            color: { background: rgba, border: rgba, highlight: { background: rgba, border: rgba } },
            font: { color: `rgba(255,255,255,${fontOpacity})` },
        });
    }
    nodesDataSet.update(updates);
}

function resetBrightness() {
    const updates = [];
    for (const id in nodeBaseColors) {
        updates.push({ id, color: nodeBaseColors[id], font: { color: "#fff" } });
    }
    nodesDataSet.update(updates);
}

document.getElementById("close-panel").addEventListener("click", () => {
    document.getElementById("detail-panel").hidden = true;
});

document.getElementById("toggle-panel").addEventListener("click", () => {
    const panel = document.getElementById("detail-panel");
    panel.hidden = !panel.hidden;
});

// Zoom controls
function focusNode(nodeId) {
    if (!network || !nodeId) return;
    const pos = network.getPositions([nodeId])[nodeId];
    if (!pos) return;
    network.moveTo({
        position: { x: pos.x, y: pos.y },
        scale: 2.5,
        animation: { duration: 500, easingFunction: "easeInOutQuad" },
    });
    network.selectNodes([nodeId]);
}

document.getElementById("zoom-word").addEventListener("click", () => focusNode(wordNodeId));
document.getElementById("zoom-root").addEventListener("click", () => focusNode(rootNodeId));

document.getElementById("zoom-fit").addEventListener("click", () => {
    if (!network) return;
    network.fit({
        animation: { duration: 500, easingFunction: "easeInOutQuad" },
    });
});

// Etymology link mode: persist preference
const etymLinkSelect = document.getElementById("etym-link-mode");
etymLinkSelect.value = localStorage.getItem("etymLinkMode") || "app";
etymLinkSelect.addEventListener("change", () => {
    localStorage.setItem("etymLinkMode", etymLinkSelect.value);
});

// Delegated click handler for etymology links
document.getElementById("detail-etym").addEventListener("click", (e) => {
    const link = e.target.closest("a.etym-link");
    if (!link) return;
    e.preventDefault();
    const word = link.dataset.word;
    const langCode = link.dataset.langCode;
    const mode = etymLinkSelect.value;

    if (mode === "wikt") {
        const url = word.startsWith("*")
            ? `https://en.wiktionary.org/wiki/Reconstruction:${encodeURIComponent(langCode)}/${encodeURIComponent(word.replace(/^\*/, ""))}`
            : `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
        window.open(url, "_blank", "noopener");
    } else {
        // In-app mode: look up full language name from graph nodes, then load full tree
        if (typeof selectWord === "function") {
            const nodeId = currentNodes.find(n => {
                const [w] = n.id.split(":");
                return w === word;
            });
            const fullLang = nodeId ? nodeId.language : undefined;
            selectWord(word, fullLang);
        }
    }
});
