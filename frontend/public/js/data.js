// Hardcoded etymology data for prototype
// Color scheme: Germanic=blue, Romance/Latin=red, Greek=green, PIE=gold, Other=gray

const COLORS = {
    germanic: "#4a90d9",
    romance: "#d94a4a",
    greek: "#4abd8c",
    pie: "#d4a843",
    other: "#888",
};

function langColor(lang) {
    if (/english|german|norse|dutch|frisian|gothic|proto-germanic/i.test(lang)) return COLORS.germanic;
    if (/latin|italic|french|spanish|portuguese|romanian|proto-italic/i.test(lang)) return COLORS.romance;
    if (/greek/i.test(lang)) return COLORS.greek;
    if (/proto-indo-european/i.test(lang)) return COLORS.pie;
    return COLORS.other;
}

function makeNode(word, lang, level) {
    return {
        id: `${word}:${lang}`,
        label: `${word}\n(${lang})`,
        color: langColor(lang),
        font: { color: "#fff" },
        level,
    };
}

function makeEdge(fromWord, fromLang, toWord, toLang, type) {
    return {
        from: `${fromWord}:${fromLang}`,
        to: `${toWord}:${toLang}`,
        label: type,
        arrows: "to",
        dashes: type === "borrowed",
    };
}

const ETYMOLOGIES = {
    wine: {
        nodes: [
            makeNode("wine", "English", 0),
            makeNode("win", "Middle English", 1),
            makeNode("wīn", "Old English", 2),
            makeNode("*wīną", "Proto-Germanic", 3),
            makeNode("vīnum", "Latin", 4),
            makeNode("*wīnom", "Proto-Italic", 5),
            makeNode("*wóyh₁nom", "Proto-Indo-European", 6),
        ],
        edges: [
            makeEdge("wine", "English", "win", "Middle English", "inherited"),
            makeEdge("win", "Middle English", "wīn", "Old English", "inherited"),
            makeEdge("wīn", "Old English", "*wīną", "Proto-Germanic", "inherited"),
            makeEdge("*wīną", "Proto-Germanic", "vīnum", "Latin", "borrowed"),
            makeEdge("vīnum", "Latin", "*wīnom", "Proto-Italic", "inherited"),
            makeEdge("*wīnom", "Proto-Italic", "*wóyh₁nom", "Proto-Indo-European", "inherited"),
        ],
    },
    water: {
        nodes: [
            makeNode("water", "English", 0),
            makeNode("wæter", "Old English", 1),
            makeNode("*watōr", "Proto-Germanic", 2),
            makeNode("*wódr̥", "Proto-Indo-European", 3),
        ],
        edges: [
            makeEdge("water", "English", "wæter", "Old English", "inherited"),
            makeEdge("wæter", "Old English", "*watōr", "Proto-Germanic", "inherited"),
            makeEdge("*watōr", "Proto-Germanic", "*wódr̥", "Proto-Indo-European", "inherited"),
        ],
    },
    mother: {
        nodes: [
            makeNode("mother", "English", 0),
            makeNode("moder", "Middle English", 1),
            makeNode("mōdor", "Old English", 2),
            makeNode("*mōdēr", "Proto-Germanic", 3),
            makeNode("*méh₂tēr", "Proto-Indo-European", 4),
        ],
        edges: [
            makeEdge("mother", "English", "moder", "Middle English", "inherited"),
            makeEdge("moder", "Middle English", "mōdor", "Old English", "inherited"),
            makeEdge("mōdor", "Old English", "*mōdēr", "Proto-Germanic", "inherited"),
            makeEdge("*mōdēr", "Proto-Germanic", "*méh₂tēr", "Proto-Indo-European", "inherited"),
        ],
    },
    father: {
        nodes: [
            makeNode("father", "English", 0),
            makeNode("fader", "Middle English", 1),
            makeNode("fæder", "Old English", 2),
            makeNode("*fadēr", "Proto-Germanic", 3),
            makeNode("*ph₂tḗr", "Proto-Indo-European", 4),
        ],
        edges: [
            makeEdge("father", "English", "fader", "Middle English", "inherited"),
            makeEdge("fader", "Middle English", "fæder", "Old English", "inherited"),
            makeEdge("fæder", "Old English", "*fadēr", "Proto-Germanic", "inherited"),
            makeEdge("*fadēr", "Proto-Germanic", "*ph₂tḗr", "Proto-Indo-European", "inherited"),
        ],
    },
    three: {
        nodes: [
            makeNode("three", "English", 0),
            makeNode("thrē", "Middle English", 1),
            makeNode("þrēo", "Old English", 2),
            makeNode("*þrīz", "Proto-Germanic", 3),
            makeNode("*tréyes", "Proto-Indo-European", 4),
        ],
        edges: [
            makeEdge("three", "English", "thrē", "Middle English", "inherited"),
            makeEdge("thrē", "Middle English", "þrēo", "Old English", "inherited"),
            makeEdge("þrēo", "Old English", "*þrīz", "Proto-Germanic", "inherited"),
            makeEdge("*þrīz", "Proto-Germanic", "*tréyes", "Proto-Indo-European", "inherited"),
        ],
    },
};

const WORD_LIST = Object.keys(ETYMOLOGIES);
