import { test as base, expect } from "@playwright/test";
import { createRandom, seed } from "./random.js";

// Key under which the theme saves the cookie choice (shop/themes/ciocia/assets/js/custom.js, #62)
const COOKIE_CONSENT_KEY = "ciocia_cookie_consent";

export const test = base.extend({
  // Cookie panel from the theme: saved as accepted before every page load, so it never covers buttons.
  // A test that checks the panel itself turns this off with test.use({ acceptCookies: false }).
  acceptCookies: [true, { option: true }],

  page: async ({ page, acceptCookies }, use) => {
    if (acceptCookies) {
      await page.addInitScript(
        ({ key, value }) => {
          try {
            globalThis.localStorage.setItem(key, value);
          } catch {
            // about:blank has no localStorage; the shop's pages do
          }
        },
        {
          key: COOKIE_CONSENT_KEY,
          value: JSON.stringify({ necessary: true, analytics: false, ads: false }),
        },
      );
    }
    await use(page);
  },

  // A fresh generator per test: the same seed gives the same picks, whatever ran before
  rng: async ({}, use) => {
    await use(createRandom(seed));
  },

  // Console errors and uncaught page errors, for the "0 JavaScript errors" checks (W3)
  consoleErrors: async ({ page }, use) => {
    const errors = [];
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await use(errors);
  },

  // Writes the seed into the HTML and JUnit report of every test
  seedAnnotation: [
    async ({}, use, testInfo) => {
      testInfo.annotations.push({ type: "seed", description: String(seed) });
      await use();
    },
    { auto: true },
  ],
});

export { expect };