import { test, expect } from "../support/fixtures.js";
import { AccountPage } from "../pages/account.js";
import { CartPage } from "../pages/cart.js";
import { CatalogPage } from "../pages/catalog.js";
import { cartSnapshot } from "../support/cart-state.js";
import { newCustomer } from "../support/data.js";
import { mailpitUrl, messagesTo } from "../support/mailpit.js";

// Step 1: 2 categories × 5 products, 1–3 of each. Small quantities also keep the cart far below 50 kg,
// above which no carrier delivers (#47) and step 7 could not choose one.
const CATEGORY_COUNT = 2;
const PRODUCTS_PER_CATEGORY = 5;
const MAX_QUANTITY = 3;

// The W4 scenario is one test: every step needs what the previous one left (cart, customer, order).
// Issues E2E 2/5 to 5/5 replace each test.step.skip with the real step.
test("W4: from an empty cart to the VAT invoice", async ({ page, request, rng }) => {
  // eslint-disable-next-line no-unused-vars -- used by steps 2–3 (rest of E2E 2/5)
  const addedProducts = await test.step("1. Add 10 products in varying quantities from 2 categories to the cart", async () => {
    const catalog = new CatalogPage(page);
    const cart = new CartPage(page);

    // Quantities planned up front, so there are always at least two different values
    const quantities = Array.from({ length: CATEGORY_COUNT * PRODUCTS_PER_CATEGORY }, () => rng.int(1, MAX_QUANTITY));
    if (new Set(quantities).size === 1) {
      quantities[0] = (quantities[0] % MAX_QUANTITY) + 1;
    }

    // Categories in an order drawn from the seed; one whose list is too short is passed over
    const categories = await catalog.categories();
    const added = [];
    const usedCategories = [];
    for (const category of rng.sample(categories, categories.length)) {
      if (usedCategories.length === CATEGORY_COUNT) break;
      const planned = quantities.slice(added.length, added.length + PRODUCTS_PER_CATEGORY);
      const products = await catalog.addFromCategory(category, planned, rng, new Set(added.map((p) => p.productId)));
      if (products) {
        usedCategories.push(category.name);
        added.push(...products);
      }
    }
    expect(
      usedCategories.length,
      `categories with ${PRODUCTS_PER_CATEGORY} products that can be added, of: ${categories.map((c) => c.name).join(", ")}`,
    ).toBe(CATEGORY_COUNT);
    test.info().annotations.push(
      { type: "categories", description: usedCategories.join(", ") },
      { type: "cart after step 1", description: added.map((p) => `${p.quantity} × ${p.name}`).join("; ") },
    );

    await cart.openFromHeader();
    const expected = added.map(({ id, quantity }) => ({ id, quantity })).sort((a, b) => a.id.localeCompare(b.id));
    expect(await cart.lineQuantities(), "cart lines and their quantities").toEqual(expected);
    const totalQuantity = added.reduce((sum, p) => sum + p.quantity, 0);
    await expect(cart.headerCount, "header cart count = sum of the quantities").toHaveText(String(totalQuantity));
    return added;
  });
  await test.step.skip("2. Search by name and add a random result to the cart", async () => {});
  await test.step.skip("3. Remove 3 products from the cart", async () => {});

  // Steps 9–10 log in again with this e-mail and password
  // eslint-disable-next-line no-unused-vars -- used by steps 9–10 (E2E 5/5)
  const customer = await test.step("4. Register a new account", async () => {
    const account = new AccountPage(page);
    const customer = newCustomer();

    // Registration starts from the header, as a customer would do it
    await page.goto("/");
    const cartBefore = await cartSnapshot(page);
    await account.openRegistrationFromHeader();
    await account.register(customer);

    await expect(account.headerAccountLink).toBeVisible();
    await expect(account.headerLoginLink).toHaveCount(0);
    expect(await account.loggedInCustomer()).toEqual({
      isLogged: true,
      email: customer.email,
      firstName: customer.firstName,
      lastName: customer.lastName,
    });
    // A guest's cart moves to the new account; nothing may be lost or added on the way
    expect(await cartSnapshot(page), "cart after registration").toEqual(cartBefore);

    if (mailpitUrl) {
      await test.step("Welcome e-mail arrives in Mailpit", async () => {
        await expect
          .poll(async () => (await messagesTo(request, customer.email)).length, {
            message: `no e-mail to ${customer.email} in Mailpit (${mailpitUrl})`,
            timeout: 15_000,
          })
          .toBeGreaterThan(0);
      });
    }
    return customer;
  });

  await test.step.skip("5. Order the cart contents", async () => {});
  await test.step.skip("6. Choose cash on delivery", async () => {});
  await test.step.skip("7. Choose one of the two new carriers", async () => {});
  await test.step.skip("8. Confirm the order", async () => {});
  await test.step.skip("9. Check the order status", async () => {});
  await test.step.skip("10. Download the VAT invoice", async () => {});
});
