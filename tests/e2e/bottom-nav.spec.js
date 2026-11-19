import { test, expect } from "../support/fixtures.js";
import { BottomNav } from "../pages/bottom-nav.js";

// The bar exists only below 768 px; 375 px is the width compared with the source shop (issue #32).
test.use({ viewport: { width: 375, height: 812 } });

test.describe("mobile bottom bar", () => {
  test("shows five shortcuts on phones and is gone from 768 px", async ({ page, consoleErrors }) => {
    const bar = new BottomNav(page);
    await page.goto("/");
    await expect(bar.nav).toBeVisible();
    await expect(bar.items).toHaveCount(5);
    // A new visitor has an empty cart, so there is no count badge
    await expect(bar.cartBadge).toBeHidden();

    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(bar.nav).toBeHidden();
    expect(consoleErrors).toEqual([]);
  });

  test("Kategorie opens the drawer and Escape gives focus back", async ({ page }) => {
    const bar = new BottomNav(page);
    await page.goto("/");
    await bar.categories.click();
    await expect(bar.drawer).toBeVisible();
    await expect(bar.drawer).toHaveAttribute("role", "dialog");

    await page.keyboard.press("Escape");
    await expect(bar.drawer).toBeHidden();
    await expect(bar.categories).toBeFocused();
  });

  test("Szukaj opens the search dialog and submits to the search page", async ({ page }) => {
    const bar = new BottomNav(page);
    await page.goto("/");
    await bar.search.click();
    await expect(bar.searchDialog).toBeVisible();
    await expect(bar.searchInput).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(bar.searchDialog).toBeHidden();
    await expect(bar.search).toBeFocused();

    await bar.search.click();
    await bar.searchInput.fill("kubek");
    await bar.searchInput.press("Enter");
    await expect(page).toHaveURL(/[?&]s=kubek/);
  });

  test("Koszyk leads to the cart and is marked as the current page there", async ({ page }) => {
    const bar = new BottomNav(page);
    await page.goto("/");
    await bar.cart.click();
    await expect(page).toHaveURL(/koszyk/);
    await expect(bar.cart).toHaveAttribute("aria-current", "page");
  });

  test("widening past 768 px with the drawer open unlocks the page", async ({ page }) => {
    const bar = new BottomNav(page);
    const wrapper = page.locator("#wrapper");
    const footer = page.locator("#footer");
    await page.goto("/");
    await bar.categories.click();
    await expect(bar.drawer).toBeVisible();
    await expect(wrapper).toHaveJSProperty("inert", true);

    // From 768 px hidden-md-up hides the drawer, but setDrawer(false) must still undo the lock
    await page.setViewportSize({ width: 800, height: 1024 });
    await expect(wrapper).toHaveJSProperty("inert", false);
    await expect(footer).toHaveJSProperty("inert", false);
    await expect.poll(() => page.locator("body").evaluate((body) => body.style.overflow)).toBe("");
  });
});
