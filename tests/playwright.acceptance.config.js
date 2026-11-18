// Playwright settings for the acceptance checks (tests/acceptance/): the crawler and the console check, which
// measure the lecturer's W3 metrics on a shop with all products. Run from tests/: npm run acceptance
// Kept out of npm test (testDir ./e2e there), because the crawl takes minutes and needs the full data.
// Everything else (shop address, seed, browser) is as in playwright.config.js.
import { defineConfig } from "@playwright/test";
import e2e from "./playwright.config.js";

export default defineConfig({
  ...e2e,
  testDir: "./acceptance",
  // Emptied when a run starts; also holds metrics.tsv, the rows for the acceptance table (support/acceptance.js)
  outputDir: "./acceptance-report/test-results",
  // The crawl sets its own longer timeout
  globalTimeout: 20 * 60_000,
  reporter: [
    ["list"],
    ["html", { outputFolder: "acceptance-report/html", open: "never" }],
    ["junit", { outputFile: "acceptance-report/junit.xml", embedAnnotationsAsProperties: true }],
  ],
});
