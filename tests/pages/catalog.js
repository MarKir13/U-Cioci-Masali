import { expect } from "../support/fixtures.js";
import { headerCartCount } from "./cart.js";

// Whether a product from openProduct() can be added in this quantity: the shop allows it (not out of stock,
// no required customisation), it has enough stock, and the quantity reaches its minimum.
// `stock` already excludes what is in the cart: PrestaShop's Product::getQuantity() subtracts the cart
// quantity before the product page puts it into data-product, so a product the cart already holds needs no
// correction here (checked on the shop: 299, 298 after adding 1, 0 and a disabled button after adding the rest).
export function canBeAdded(product, quantity) {
  return product.canAdd && product.stock >= quantity && product.minimalQuantity <= quantity;
}

// Catalogue: categories of the top menu, their product lists and the product page with "Dodaj do koszyka".
// The ciocia theme overrides only the menu; the category and product templates are Classic's, so the
// selectors are Classic ids and classes. Nothing here depends on product names or ids, because the same
// test runs on the demo products now and on the imported ones later.
export class CatalogPage {
  constructor(page) {
    this.page = page;
    // Top-level categories (shop/themes/ciocia/modules/ps_mainmenu): CMS pages and links are other <li> types.
    // Their subcategories are in the hidden submenu inside the same <li>.
    this.topMenuCategories = page.locator('#_desktop_top_menu ul[data-depth="0"] > li.category');
    this.miniatures = page.locator("#js-product-list .product-miniature");

    // Product page. data-product holds the product as the shop presents it (ids, name, stock).
    this.productDetails = page.locator("#product-details");
    this.quantityInput = page.locator("#quantity_wanted");
    // Disabled by the shop when the product cannot be bought as it is (no stock, required customisation)
    this.addToCartButton = page.locator('.product-add-to-cart button[data-button-action="add-to-cart"]');
    // "Produkt dodany poprawnie do Twojego koszyka", from ps_shoppingcart
    this.addedModal = page.locator("#blockcart-modal");
    this.addedModalName = this.addedModal.locator(".product-name");
    this.continueShoppingButton = this.addedModal.locator('button.btn-secondary[data-dismiss="modal"]');
    this.headerCartCount = headerCartCount(page);
  }

  // Categories to choose from, as { name, url, subcategories: [{ name, url }] }: E2E_CATEGORIES
  // (comma-separated category URLs, no subcategories) when set, otherwise the top menu with its submenus
  async categories() {
    const fromEnv = (process.env.E2E_CATEGORIES ?? "")
      .split(",")
      .map((url) => url.trim())
      .filter(Boolean);
    if (fromEnv.length > 0) {
      return fromEnv.map((url) => ({ name: url, url, subcategories: [] }));
    }
    await this.page.goto("/");
    const categories = await this.topMenuCategories.evaluateAll((items) =>
      items.map((li) => {
        const link = (a) => ({ name: a.textContent.trim(), url: a.href });
        const subLinks = li.querySelectorAll(':scope > div > ul[data-depth="1"] > li.category > a');
        return { ...link(li.querySelector(":scope > a")), subcategories: [...subLinks].map(link) };
      }),
    );
    expect(categories.length, "categories in the top menu").toBeGreaterThan(0);
    return categories;
  }

  // A category and then its subcategories, in an order drawn from the seed. On the shop a top-level category
  // may list no products of its own, when they are assigned only to its subcategories.
  static withSubcategories(category, rng) {
    const subcategories = category.subcategories.map((sub) => ({ ...sub, name: `${category.name} › ${sub.name}` }));
    return [category, ...rng.sample(subcategories, subcategories.length)];
  }

  // Products on page 1 of a category's list, without those the list already marks as out of stock
  async listedProducts(category) {
    await this.page.goto(category.url);
    await expect(this.page.locator("body#category"), `category page ${category.url}`).toBeVisible();
    return this.shownProducts();
  }

  // Products on the open list (category or search results), without those marked as out of stock.
  // The product page has the last word: openProduct() tells whether a product can really be added.
  async shownProducts() {
    return this.miniatures.evaluateAll((items) =>
      items
        .filter((item) => !item.querySelector(".product-flag.out_of_stock"))
        .map((item) => ({
          productId: item.dataset.idProduct,
          url: item.querySelector("a.product-thumbnail").href,
        })),
    );
  }

  async openProduct(url) {
    await this.page.goto(url);
    await expect(this.page.locator("body#product")).toBeVisible();
    const product = JSON.parse(await this.productDetails.getAttribute("data-product"));
    return {
      // Same id as a cart line: "<id_product>-<id_product_attribute>"
      id: `${product.id_product}-${product.id_product_attribute}`,
      productId: String(product.id_product),
      name: product.name,
      stock: Number(product.quantity),
      minimalQuantity: Number(product.minimal_quantity) || 1,
      canAdd: await this.addToCartButton.isEnabled(),
    };
  }

  // On the open product page. Waits for the shop's answer, the modal, then for the header counter,
  // so the next page is never opened before the cart has been saved.
  async addToCart(product, quantity) {
    const countBefore = Number(await this.headerCartCount.innerText());
    await this.quantityInput.fill(String(quantity));
    await this.addToCartButton.click();
    await expect(this.addedModal, `"added to cart" window for ${product.name}`).toBeVisible();
    await expect(this.addedModalName).toHaveText(product.name);
    await this.continueShoppingButton.click();
    await expect(this.addedModal).toBeHidden();
    await expect(this.headerCartCount, `header cart count after adding ${quantity} × ${product.name}`).toHaveText(
      String(countBefore + quantity),
    );
  }

  // Adds one product per planned quantity from a category, in an order drawn from the seed. A product that
  // cannot take its planned quantity (see canBeAdded) is skipped. Products in `skipProductIds` (already in the
  // cart from another category) are skipped too.
  // The products are all chosen first and added only then, so when the category has too few that fit, it
  // returns null with nothing added and the caller tries another category.
  async addFromCategory(category, quantities, rng, skipProductIds) {
    const listed = (await this.listedProducts(category)).filter((item) => !skipProductIds.has(item.productId));
    if (listed.length < quantities.length) {
      return null;
    }
    const chosen = [];
    for (const item of rng.sample(listed, listed.length)) {
      if (chosen.length === quantities.length) break;
      const quantity = quantities[chosen.length];
      const product = await this.openProduct(item.url);
      if (canBeAdded(product, quantity)) {
        chosen.push({ ...product, quantity, category: category.name, url: item.url });
      }
    }
    if (chosen.length < quantities.length) {
      return null;
    }
    // None of them is in the cart yet, so their stock is the same as when they were chosen
    for (const product of chosen) {
      await this.openProduct(product.url);
      await this.addToCart(product, product.quantity);
    }
    return chosen;
  }

  // addFromCategory() on the category, or else on its subcategories one by one (see withSubcategories)
  async addFromCategoryOrSubcategory(category, quantities, rng, skipProductIds) {
    for (const candidate of CatalogPage.withSubcategories(category, rng)) {
      const added = await this.addFromCategory(candidate, quantities, rng, skipProductIds);
      if (added) return added;
    }
    return null;
  }
}
