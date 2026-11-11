// Playwright settings for the W4 scenario. Run from tests/: npm test
import { defineConfig, devices } from "@playwright/test";

// One seed per run. Set here, in the main process, so every worker gets the same value,
// including a worker restarted after a failure. Repeat a run with E2E_SEED=<seed from the report>.
process.env.E2E_SEED ||= String(Math.floor(Math.random() * 2 ** 31));
if (!/^\d+$/.test(process.env.E2E_SEED)) {
  throw new Error(`E2E_SEED must be a non-negative integer, got "${process.env.E2E_SEED}"`);
}

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  workers: 1,
  fullyParallel: false,
  // W4 counts real passes (3 of 3); a retry would hide a flaky step
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  // The whole run must fit in 5 minutes; stop well before that
  globalTimeout: 4 * 60_000,
  // The scenario is one long test, so the 30 s default is too short
  timeout: 3 * 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["junit", { outputFile: "test-results/junit.xml", embedAnnotationsAsProperties: true }],
  ],
  use: {
    baseURL: process.env.BASE_URL || "https://localhost:8443",
    // Self-signed certificate from the proxy container (ADR 0002)
    ignoreHTTPSErrors: true,
    headless: true,
    locale: "pl-PL",
    timezoneId: "Europe/Warsaw",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});