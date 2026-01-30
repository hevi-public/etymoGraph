function selectWord(word) {
    const data = ETYMOLOGIES[word];
    if (data) {
        updateGraph(data);
    }
}

// Load default word on startup
selectWord("wine");
