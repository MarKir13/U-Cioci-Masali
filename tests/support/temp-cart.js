// TEMPORARY (issue #54): stands in for steps 1–3 (issue #52) until they land, so that steps 5–8 have a cart
// to order. Delete this file and its call in order.spec.js when #52 is merged.
import { expect } from "./fixtures.js";

// Puts the first product from the home page into the cart, from its product page
export async function addFirstHomeProductToCart(page) {
  await page.goto("/");
  await page.locator(".js-product-miniature a.product-thumbnail").first().click();
  await expect(page.locator("body#product")).toBeVisible();
  await page.locator('button[data-button-action="add-to-cart"]').click();
  // The shop confirms with a modal once the product is in the cart
  await expect(page.locator("#blockcart-modal")).toBeVisible();
}
