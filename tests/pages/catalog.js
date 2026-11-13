import { expect } from "../support/fixtures.js";
import { headerCartCount } from "./cart.js";

// Catalogue: categories of the top menu, their product lists and the product page with "Dodaj do koszyka".
// The ciocia theme overrides only the menu; the category and product templates are Classic's, so the
// selectors are Classic ids and classes. Nothing here depends on product names or ids, because the same
// test runs on the demo products now and on the imported ones later.
export class CatalogPage {
  constructor(page) {
    this.page = page;
    // Top-level categories only (shop/themes/ciocia/modules/ps_mainmenu): CMS pages and links are other <li> types
    this.topMenuCategoryLinks = page.locator('#_desktop_top_menu ul[data-depth="0"] > li.category > a');
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

  // Categories to choose from: E2E_CATEGORIES (comma-separated category URLs) when set, otherwise the top menu
  async categories() {
    const fromEnv = (process.env.E2E_CATEGORIES ?? "")
      .split(",")
      .map((url) => url.trim())
      .filter(Boolean);
    if (fromEnv.length > 0) {
      return fromEnv.map((url) => ({ name: url, url }));
    }
    await this.page.goto("/");
    const links = await this.topMenuCategoryLinks.evaluateAll((anchors) =>
      anchors.map((a) => ({ name: a.textContent.trim(), url: a.href })),
    );
    expect(links.length, "categories in the top menu").toBeGreaterThan(0);
    return links;
  }

  // Products on page 1 of a category's list, without those the list already marks as out of stock.
  // The product page has the last word: openProduct() tells whether a product can really be added.
  async listedProducts(category) {
    await this.page.goto(category.url);
    await expect(this.page.locator("body#category"), `category page ${category.url}`).toBeVisible();
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
  // cannot take its planned quantity (out of stock, too little stock, higher minimum, required customisation)
  // is skipped. Products in `skipProductIds` (already in the cart from another category) are skipped too.
  // Returns null, with nothing added, when the list is too short to try; the caller then tries another category.
  async addFromCategory(category, quantities, rng, skipProductIds) {
    const listed = (await this.listedProducts(category)).filter((item) => !skipProductIds.has(item.productId));
    if (listed.length < quantities.length) {
      return null;
    }
    const added = [];
    for (const item of rng.sample(listed, listed.length)) {
      if (added.length === quantities.length) break;
      const quantity = quantities[added.length];
      const product = await this.openProduct(item.url);
      if (!product.canAdd || product.stock < quantity || product.minimalQuantity > quantity) continue;
      await this.addToCart(product, quantity);
      added.push({ ...product, quantity, category: category.name });
    }
    expect(
      added.length,
      `products of "${category.name}" that could be added in their planned quantity (set E2E_CATEGORIES to pick others)`,
    ).toBe(quantities.length);
    return added;
  }
}
