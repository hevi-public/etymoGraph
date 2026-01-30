const searchInput = document.getElementById("search-input");
const suggestions = document.getElementById("suggestions");
const clearBtn = document.getElementById("clear-btn");

let debounceTimer = null;

function renderSuggestions(matches) {
    suggestions.innerHTML = "";
    if (matches.length === 0) {
        suggestions.hidden = true;
        return;
    }
    matches.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item.word;
        li.addEventListener("click", () => {
            searchInput.value = item.word;
            suggestions.hidden = true;
            selectWord(item.word);
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

searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        const q = searchInput.value.trim();
        if (q) {
            suggestions.hidden = true;
            selectWord(q);
        }
    }
});

document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-container")) {
        suggestions.hidden = true;
    }
});
