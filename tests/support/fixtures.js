import { test as base, expect } from "@playwright/test";
import { createRandom, seed } from "./random.js";

export const test = base.extend({
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