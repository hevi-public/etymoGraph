// ESLint v9+ flat config format
export default [
    {
        files: ["frontend/public/js/**/*.js"],
        languageOptions: {
            ecmaVersion: "latest",
            sourceType: "script",
            globals: {
                // Browser globals
                window: "readonly",
                document: "readonly",
                console: "readonly",
                fetch: "readonly",
                localStorage: "readonly",
                setTimeout: "readonly",
                clearTimeout: "readonly",
                // vis.js globals
                vis: "readonly",
                // App-specific globals from other files
                API_BASE: "readonly",
                searchWords: "readonly",
                getWord: "readonly",
                getEtymologyTree: "readonly",
                getEtymologyChain: "readonly",
                network: "readonly",
                searchedWordId: "readonly",
                nodeColorOverrides: "readonly",
                updateGraph: "readonly",
                centerNode: "readonly",
                centerViewport: "readonly",
                LANGUAGE_FAMILY_COLORS: "readonly",
                buildLegendHTML: "readonly",
                LAYOUTS: "readonly",
                currentLayout: "writable",
                selectWord: "readonly",
            },
        },
        rules: {
            "semi": ["error", "always"],
            "quotes": ["error", "double"],
            "indent": ["error", 4],
            "no-unused-vars": "warn",
            "no-undef": "error",
            "no-console": "off",
            "max-len": ["warn", {
                "code": 100,
                "ignoreUrls": true,
                "ignoreStrings": true,
                "ignoreTemplateLiterals": true,
            }],
        },
    },
];
