import { readFileSync } from "fs";
import { resolve } from "path";

const routerSource = readFileSync(
    resolve(__dirname, "../public/js/router.js"),
    "utf-8"
);

function loadRouter() {
    // Reset URL to clean state
    window.history.replaceState(null, "", "/");
    // Execute router IIFE in jsdom context — re-assigns window.router
    eval(routerSource);
    return window.router;
}

/** Helper: parse query string from a buildURL result into a plain object. */
function parseQS(url) {
    const params = {};
    new URLSearchParams(url.replace(/^\/\??/, "")).forEach((v, k) => {
        params[k] = v;
    });
    return params;
}

describe("parseURL", () => {
    let parseURL;

    beforeEach(() => {
        const r = loadRouter();
        parseURL = r._internals.parseURL;
    });

    it("returns all etymology defaults for empty string", () => {
        const state = parseURL("");
        expect(state).toEqual({
            view: "etymology",
            word: "wine",
            lang: "English",
            types: "inh,bor,der",
            layout: "era-layered",
        });
    });

    it("parses word and lang from URL", () => {
        const state = parseURL("?word=fire&lang=Latin");
        expect(state.word).toBe("fire");
        expect(state.lang).toBe("Latin");
        expect(state.types).toBe("inh,bor,der");
        expect(state.layout).toBe("era-layered");
    });

    it("defaults lang to English when only word is given", () => {
        const state = parseURL("?word=apple");
        expect(state.word).toBe("apple");
        expect(state.lang).toBe("English");
    });

    it("parses concept view with defaults", () => {
        const state = parseURL("?view=concept&concept=water");
        expect(state.view).toBe("concept");
        expect(state.concept).toBe("water");
        expect(state.similarity).toBe(100);
        expect(state.etymEdges).toBe(true);
        expect(state.pos).toBe("");
    });

    it("applies Number and Boolean parsers to concept params", () => {
        const state = parseURL("?view=concept&concept=fire&similarity=75&etymEdges=false");
        expect(state.similarity).toBe(75);
        expect(state.etymEdges).toBe(false);
    });

    it("falls back to etymology defaults for unknown view", () => {
        const state = parseURL("?view=nonexistent");
        expect(state.view).toBe("etymology");
        expect(state.word).toBe("wine");
    });
});

describe("buildURL", () => {
    let buildURL;

    beforeEach(() => {
        const r = loadRouter();
        buildURL = r._internals.buildURL;
    });

    it("includes all params for default etymology state", () => {
        const url = buildURL({
            view: "etymology",
            word: "wine",
            lang: "English",
            types: "inh,bor,der",
            layout: "era-layered",
        });
        const qs = parseQS(url);
        expect(qs.view).toBe("etymology");
        expect(qs.word).toBe("wine");
        expect(qs.lang).toBe("English");
        expect(qs.types).toBe("inh,bor,der");
        expect(qs.layout).toBe("era-layered");
    });

    it("includes non-default word alongside all other params", () => {
        const url = buildURL({
            view: "etymology",
            word: "fire",
            lang: "English",
            types: "inh,bor,der",
            layout: "era-layered",
        });
        const qs = parseQS(url);
        expect(qs.word).toBe("fire");
        expect(qs.lang).toBe("English");
    });

    it("includes all concept params", () => {
        const url = buildURL({
            view: "concept",
            concept: "water",
            pos: "",
            similarity: 100,
            etymEdges: true,
        });
        const qs = parseQS(url);
        expect(qs.view).toBe("concept");
        expect(qs.concept).toBe("water");
        expect(qs.similarity).toBe("100");
        expect(qs.etymEdges).toBe("true");
    });

    it("reflects non-default similarity", () => {
        const url = buildURL({
            view: "concept",
            concept: "fire",
            pos: "",
            similarity: 75,
            etymEdges: true,
        });
        const qs = parseQS(url);
        expect(qs.similarity).toBe("75");
    });

    it("includes default similarity (100)", () => {
        const url = buildURL({
            view: "concept",
            concept: "fire",
            pos: "",
            similarity: 100,
            etymEdges: true,
        });
        expect(url).toContain("similarity=100");
    });
});

describe("push/replace", () => {
    let router;

    beforeEach(() => {
        router = loadRouter();
        router.initialize();
    });

    it("pushState is called with correct URL on push", () => {
        const spy = vi.spyOn(window.history, "pushState");
        router.push({ word: "fire" });
        expect(spy).toHaveBeenCalledTimes(1);
        const url = spy.mock.calls[0][2];
        const qs = parseQS(url);
        expect(qs.word).toBe("fire");
        expect(qs.lang).toBe("English");
        spy.mockRestore();
    });

    it("does not pushState for duplicate push", () => {
        const spy = vi.spyOn(window.history, "pushState");
        router.push({ word: "fire" });
        router.push({ word: "fire" });
        expect(spy).toHaveBeenCalledTimes(1);
        spy.mockRestore();
    });

    it("replaceState is called (not pushState) on replace", () => {
        const pushSpy = vi.spyOn(window.history, "pushState");
        const replaceSpy = vi.spyOn(window.history, "replaceState");
        router.replace({ types: "inh" });
        expect(pushSpy).not.toHaveBeenCalled();
        // replaceState is called by both initialize() and replace() — check the last call
        const lastCall = replaceSpy.mock.calls[replaceSpy.mock.calls.length - 1];
        const qs = parseQS(lastCall[2]);
        expect(qs.types).toBe("inh");
        pushSpy.mockRestore();
        replaceSpy.mockRestore();
    });

    it("fills concept defaults and discards etymology params on view change", () => {
        const spy = vi.spyOn(window.history, "pushState");
        router.push({ view: "concept", concept: "water" });
        const state = spy.mock.calls[0][0];
        expect(state.view).toBe("concept");
        expect(state.concept).toBe("water");
        expect(state.similarity).toBe(100);
        expect(state.etymEdges).toBe(true);
        // Etymology params should not be present
        expect(state.word).toBeUndefined();
        expect(state.lang).toBeUndefined();
        spy.mockRestore();
    });
});

describe("roundtrip", () => {
    let parseURL, buildURL;

    beforeEach(() => {
        const r = loadRouter();
        parseURL = r._internals.parseURL;
        buildURL = r._internals.buildURL;
    });

    it("buildURL → parseURL produces identical state", () => {
        const original = {
            view: "concept",
            concept: "fire",
            pos: "noun",
            similarity: 75,
            etymEdges: false,
        };
        const url = buildURL(original);
        const parsed = parseURL(url.replace("/", ""));
        expect(parsed).toEqual(original);
    });

    it("parseURL → buildURL produces identical URL", () => {
        const url = "?view=etymology&word=fire&lang=Latin&types=inh,bor&layout=force-directed";
        const state = parseURL(url);
        const rebuilt = buildURL(state);
        const originalParams = new URLSearchParams(url);
        const rebuiltParams = new URLSearchParams(rebuilt.replace(/^\/\??/, ""));
        for (const [key, val] of originalParams) {
            expect(rebuiltParams.get(key)).toBe(val);
        }
        for (const [key, val] of rebuiltParams) {
            expect(originalParams.get(key)).toBe(val);
        }
    });
});
