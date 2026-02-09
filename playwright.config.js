import { defineConfig } from "@playwright/test";
export default defineConfig({
    testDir: "tests/e2e",
    timeout: 30000,
    use: {
        baseURL: "http://localhost:8080",
        actionTimeout: 5000,
        screenshot: "only-on-failure",
    },
    projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
