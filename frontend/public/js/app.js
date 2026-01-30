async function selectWord(word) {
    try {
        const data = await getEtymologyTree(word);
        if (data.nodes.length === 0) {
            data.nodes = [{ id: `${word}:English`, label: word, language: "English", level: 0 }];
        }
        updateGraph(data);
    } catch (e) {
        console.error("Failed to load etymology:", e);
    }
}

// Load default word on startup
selectWord("wine");
