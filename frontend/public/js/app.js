let currentWord = "wine";

function getSelectedTypes() {
    const checkboxes = document.querySelectorAll("#filter-dropdown input[type=checkbox]:checked");
    const types = Array.from(checkboxes).map((cb) => cb.value);
    return types.length > 0 ? types.join(",") : "inh";
}

async function selectWord(word) {
    currentWord = word;
    try {
        const types = getSelectedTypes();
        const data = await getEtymologyTree(word, "English", types);
        if (data.nodes.length === 0) {
            data.nodes = [{ id: `${word}:English`, label: word, language: "English", level: 0 }];
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
    selectWord(currentWord);
});

// Load default word on startup
selectWord("wine");
