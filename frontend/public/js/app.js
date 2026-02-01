let currentWord = "wine";
let currentLang = "English";

function getSelectedTypes() {
    const checkboxes = document.querySelectorAll("#filter-dropdown input[type=checkbox]:checked");
    const types = Array.from(checkboxes).map((cb) => cb.value);
    return types.length > 0 ? types.join(",") : "inh";
}

async function resolveLanguage(word) {
    try {
        const data = await searchWords(word);
        const exact = data.results.find((r) => r.word.toLowerCase() === word.toLowerCase());
        return exact ? exact.lang : (data.results[0] ? data.results[0].lang : "English");
    } catch (_) {
        return "English";
    }
}

async function selectWord(word, lang) {
    if (!lang) {
        lang = await resolveLanguage(word);
    }
    currentWord = word;
    currentLang = lang;
    try {
        const types = getSelectedTypes();
        const data = await getEtymologyTree(word, lang, types);
        if (data.nodes.length === 0) {
            data.nodes = [{ id: `${word}:${lang}`, label: word, language: lang, level: 0 }];
        }
        updateGraph(data);
    } catch (e) {
        console.error("Failed to load etymology:", e);
    }
}

// Filter dropdown toggle
const filterBtn = document.getElementById("filter-btn");
const filterDropdown = document.getElementById("filter-dropdown");

filterBtn.addEventListener("click", () => {
    filterDropdown.classList.toggle("open");
});

document.addEventListener("click", (e) => {
    if (!e.target.closest(".filter-container")) {
        filterDropdown.classList.remove("open");
    }
});

// Re-fetch when filter changes
filterDropdown.addEventListener("change", () => {
    selectWord(currentWord, currentLang);
});

// Load default word on startup
selectWord("wine", "English");
