import { test, expect } from "../support/fixtures.js";
import { BLOCKED_MESSAGE, keepToShop, recordMetric } from "../support/acceptance.js";
import { CatalogPage, canBeAdded } from "../pages/catalog.js";
import { CartPage } from "../pages/cart.js";
import { CheckoutPage } from "../pages/checkout.js";

// W3 metric: 0 JavaScript errors in the console on the home, category, product and cart pages. Checkout too,
// since it has its own header template (AGENTS.md). A customer's way through them: a category from the top menu,
// a product from its list that can be bought, that product in the cart, then "Przejdź do realizacji zamówienia".
// Category and product are drawn with the seed, so E2E_SEED repeats a run.
test("console: no JavaScript errors on home, category, product, cart and checkout", async ({
  page,
  baseURL,
  rng,
  consoleErrors,
}, testInfo) => {
  const catalog = new CatalogPage(page);
  const cart = new CartPage(page);
  const checkout = new CheckoutPage(page);
  // Requests to other hosts are counted by the crawler; here only their console message is left out
  await keepToShop(page, baseURL);

  // Every console error of the test counts, grouped by where it came: the page of a visit, or BETWEEN for what
  // happens outside the visits (pages opened while choosing the category and product, adding to the cart)
  const BETWEEN = "between the pages: choosing a category and a product, adding to the cart";
  const errorsByPage = {};
  let taken = 0;
  // Moves the errors that came since the last call to `label`
  function take(label) {
    const fresh = consoleErrors.slice(taken).filter((text) => !text.includes(BLOCKED_MESSAGE));
    taken = consoleErrors.length;
    if (fresh.length > 0 || label !== BETWEEN) {
      errorsByPage[label] = [...(errorsByPage[label] ?? []), ...fresh];
    }
  }
  async function visit(name, open) {
    take(BETWEEN);
    await open();
    await page.waitForLoadState("load");
    take(name);
  }

  // Set once all five pages are open; until then the row says "did not finish" and fails
  let finished = false;
  try {
    await visit("home", () => page.goto("/"));

    // A category or subcategory with a product that can be added, as the E2E scenario chooses them
    const categories = await catalog.categories();
    let chosen = null;
    for (const category of rng.sample(categories, categories.length)) {
      for (const candidate of CatalogPage.withSubcategories(category, rng)) {
        const listed = await catalog.listedProducts(candidate);
        if (listed.length > 0) {
          chosen = { category: candidate, listed };
          break;
        }
      }
      if (chosen) break;
    }
    expect(chosen, "a category with products in stock").not.toBeNull();
    await visit(`category ${chosen.category.url}`, () => catalog.listedProducts(chosen.category));

    let product = null;
    for (const item of rng.sample(chosen.listed, chosen.listed.length)) {
      const candidate = await catalog.openProduct(item.url);
      if (canBeAdded(candidate, 1)) {
        product = { ...candidate, url: item.url };
        break;
      }
    }
    expect(product, `a product of ${chosen.category.url} that can be added to the cart`).not.toBeNull();
    await visit(`product ${product.url}`, () => catalog.openProduct(product.url));

    await catalog.addToCart(product, 1);
    await visit("cart", () => cart.openFromHeader());
    await visit("checkout", () => checkout.openFromCart());
    finished = true;
  } finally {
    // Also when a step threw: the report shows the pages reached so far, and the table gets its row.
    // First whatever came after the last visit (or before the step that threw).
    take(BETWEEN);
    const total = Object.values(errorsByPage).reduce((sum, errors) => sum + errors.length, 0);
    await testInfo.attach("console-errors.json", {
      body: JSON.stringify(errorsByPage, null, 2),
      contentType: "application/json",
    });
    recordMetric(
      testInfo,
      "Console errors on home, category, product, cart, checkout",
      finished ? total : "did not finish",
      0,
      0,
    );
  }
  const withErrors = Object.entries(errorsByPage).filter(([, errors]) => errors.length > 0);
  expect(Object.fromEntries(withErrors), "pages with console errors, and their errors").toEqual({});
});
