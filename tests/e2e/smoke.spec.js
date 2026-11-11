import { test, expect } from "../support/fixtures.js";

test("home page opens over HTTPS without console errors", async ({ page, baseURL, consoleErrors }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  expect(page.url()).toMatch(/^https:\/\//);
  // PrestaShop redirects other host names to its own domain (PS_DOMAIN).
  // This fails if requests silently left BASE_URL.
  expect(new URL(page.url()).origin).toBe(new URL(baseURL).origin);
  await expect(page.locator("html")).toHaveAttribute("lang", /^pl/);
  expect(consoleErrors).toEqual([]);
});