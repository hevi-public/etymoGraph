const searchInput = document.getElementById("search-input");
const suggestions = document.getElementById("suggestions");
const clearBtn = document.getElementById("clear-btn");

let debounceTimer = null;
let lastResults = [];

function renderSuggestions(matches) {
    suggestions.innerHTML = "";
    if (matches.length === 0) {
        suggestions.hidden = true;
        return;
    }
    matches.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item.word + " ";
        const langSpan = document.createElement("span");
        langSpan.className = "lang-hint";
        langSpan.textContent = item.lang;
        li.appendChild(langSpan);
        li.addEventListener("click", () => {
            searchInput.value = item.word;
            suggestions.hidden = true;
            selectWord(item.word, item.lang);
        });
        suggestions.appendChild(li);
    });
    suggestions.hidden = false;
}

searchInput.addEventListener("input", () => {
    const q = searchInput.value.trim();
    clearBtn.hidden = q === "";
    if (q === "") {
        suggestions.hidden = true;
        return;
    }
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
        try {
            const data = await searchWords(q);
            lastResults = data.results;
            renderSuggestions(data.results);
        } catch (e) {
            suggestions.hidden = true;
        }
    }, 300);
});

clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    clearBtn.hidden = true;
    suggestions.hidden = true;
    selectWord("wine");
    searchInput.focus();
});

searchInput.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
        const q = searchInput.value.trim();
        if (!q) return;
        suggestions.hidden = true;
        clearTimeout(debounceTimer);
        // Always search first to get the correct language
        try {
            const data = await searchWords(q);
            lastResults = data.results;
        } catch (_) {}
        const match = lastResults.find((r) => r.word.toLowerCase() === q.toLowerCase());
        const firstResult = match || lastResults[0];
        if (firstResult) {
            selectWord(firstResult.word, firstResult.lang);
        } else {
            selectWord(q);
        }
    }
});

document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-container")) {
        suggestions.hidden = true;
    }
});
