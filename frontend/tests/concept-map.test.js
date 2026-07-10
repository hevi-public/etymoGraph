/* global beforeAll, describe, it, expect */
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../public/js/concept-map.js"),
    "utf-8"
);

let exports_;

/**
 * concept-map.js's only load-time DOM touch is a null-tolerant getElementById,
 * so jsdom needs no setup. Its declarations are bare lexical bindings that
 * survive only inside the eval scope (see the graph-perf harness), so the
 * evaluated source re-exports the pure helpers under test as its last statement.
 */
function loadConceptMap() {
    eval(
        source +
        "\nwindow.__conceptMapTestExports = { normalizeConceptMembership, blendHexColors };"
    );
    return window.__conceptMapTestExports;
}

beforeAll(() => {
    exports_ = loadConceptMap();
});

describe("normalizeConceptMembership", () => {
    it("maps server-mode `concepts` membership onto `_concepts`", () => {
        const words = [
            { id: "brand:German", word: "brand", concepts: ["fire", "water"] },
            { id: "feuer:German", word: "feuer", concepts: ["fire"] },
        ];
        const out = exports_.normalizeConceptMembership(words);
        expect(out[0]._concepts).toEqual(["fire", "water"]);
        expect(out[1]._concepts).toEqual(["fire"]);
    });

    it("leaves client-merged words (already tagged `_concepts`) untouched", () => {
        const word = { id: "feuer:German", _concepts: ["fire"] };
        const out = exports_.normalizeConceptMembership([word]);
        expect(out[0]).toBe(word);
        expect(out[0]._concepts).toEqual(["fire"]);
    });

    it("passes words with no membership info through unchanged", () => {
        const word = { id: "fuego:Spanish", word: "fuego" };
        const out = exports_.normalizeConceptMembership([word]);
        expect(out[0]).toBe(word);
        expect("_concepts" in out[0]).toBe(false);
    });

    it("returns [] for missing input", () => {
        expect(exports_.normalizeConceptMembership(null)).toEqual([]);
        expect(exports_.normalizeConceptMembership(undefined)).toEqual([]);
    });
});

describe("blendHexColors", () => {
    it("blends the base color toward the accent by the given ratio", () => {
        // The 0.2 accent tint the multi-concept membership feeds.
        expect(exports_.blendHexColors("#000000", "#ffffff", 0.2)).toBe("rgb(51,51,51)");
        expect(exports_.blendHexColors("#ff0000", "#0000ff", 0)).toBe("rgb(255,0,0)");
        expect(exports_.blendHexColors("#ff0000", "#0000ff", 1)).toBe("rgb(0,0,255)");
    });
});
