import { expect } from "../support/fixtures.js";

// Number of items in the header cart icon (shop/themes/ciocia/modules/ps_shoppingcart): the sum of the
// quantities, refreshed by the shop after every change of the cart
export function headerCartCount(page) {
  return page.locator("#_desktop_cart .ciocia-cart-badge");
}

// Cart page. Lines are read through the attributes Classic's cart script needs (the delete link with its
// product ids, the quantity field), which the ciocia template keeps (cart-detailed-product-line.tpl).
export class CartPage {
  constructor(page) {
    this.page = page;
    this.headerCount = headerCartCount(page);
    this.headerLink = page.locator("#_desktop_cart a.ciocia-cart-link");
    this.lines = page.locator(".cart-overview .cart-item");
  }

  // From the header icon, as a customer would do it
  async openFromHeader() {
    await this.headerLink.click();
    await expect(this.page.locator("body#cart")).toBeVisible();
  }

  // Lines as shown on the page, sorted by id. The id is "<id_product>-<id_product_attribute>",
  // as in cartSnapshot (support/cart-state.js).
  async lineQuantities() {
    const lines = await this.lines.evaluateAll((items) =>
      items.map((item) => {
        const remove = item.querySelector('[data-link-action="delete-from-cart"]');
        const quantity = item.querySelector("input.js-cart-line-product-quantity");
        return {
          id: `${remove.dataset.idProduct}-${remove.dataset.idProductAttribute}`,
          quantity: Number(quantity.value),
        };
      }),
    );
    return lines.sort((a, b) => a.id.localeCompare(b.id));
  }
}
