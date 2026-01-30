const searchInput = document.getElementById("search-input");
const suggestions = document.getElementById("suggestions");
const clearBtn = document.getElementById("clear-btn");

function renderSuggestions(matches) {
    suggestions.innerHTML = "";
    if (matches.length === 0) {
        suggestions.hidden = true;
        return;
    }
    matches.forEach((word) => {
        const li = document.createElement("li");
        li.textContent = word;
        li.addEventListener("click", () => {
            searchInput.value = word;
            suggestions.hidden = true;
            selectWord(word);
        });
        suggestions.appendChild(li);
    });
    suggestions.hidden = false;
}

searchInput.addEventListener("input", () => {
    const q = searchInput.value.toLowerCase().trim();
    clearBtn.hidden = q === "";
    if (q === "") {
        suggestions.hidden = true;
        return;
    }
    const matches = WORD_LIST.filter((w) => w.startsWith(q));
    renderSuggestions(matches);
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
        const q = searchInput.value.toLowerCase().trim();
        if (ETYMOLOGIES[q]) {
            suggestions.hidden = true;
            selectWord(q);
        }
    }
});

// Close suggestions when clicking outside
document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-container")) {
        suggestions.hidden = true;
    }
});
