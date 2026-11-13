import { expect } from "../support/fixtures.js";
import { toGrosze } from "../support/price.js";

// The delete link of a cart line ("Usuń"), which carries the line's product ids
const DELETE_LINK = '[data-link-action="delete-from-cart"]';

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
    // "Suma produktów" in the summary next to the list (Classic's cart-summary-subtotals.tpl)
    this.productsSubtotal = page.locator("#cart-subtotal-products .value");
  }

  // From the header icon, as a customer would do it
  async openFromHeader() {
    await this.headerLink.click();
    await expect(this.page.locator("body#cart")).toBeVisible();
  }

  // Every line as shown on the page, sorted by id: { id, quantity, total }. The id is
  // "<id_product>-<id_product_attribute>", as in cartSnapshot (support/cart-state.js); the total is the
  // line total, in grosze. Only the line total is in <strong> inside .product-price (the unit price is not),
  // both in Classic and in the ciocia template.
  async readLines() {
    const lines = await this.lines.evaluateAll(
      (items, deleteLink) =>
        items.map((item) => {
          const remove = item.querySelector(deleteLink);
          return {
            id: `${remove.dataset.idProduct}-${remove.dataset.idProductAttribute}`,
            quantity: Number(item.querySelector("input.js-cart-line-product-quantity").value),
            total: item.querySelector(".product-price strong")?.textContent ?? "",
          };
        }),
      DELETE_LINK,
    );
    const parsed = lines.map((line) => ({ ...line, total: toGrosze(line.total) }));
    expect(
      parsed.filter((line) => line.total === null).map((line) => line.id),
      "cart lines without a line total",
    ).toEqual([]);
    return parsed.sort((a, b) => a.id.localeCompare(b.id));
  }

  // Lines as { id, quantity }, sorted by id
  async lineQuantities() {
    return (await this.readLines()).map(({ id, quantity }) => ({ id, quantity }));
  }

  async productsSubtotalGrosze() {
    return toGrosze(await this.productsSubtotal.innerText());
  }

  // The line of a product, found by the ids on its delete link
  line(id) {
    const [idProduct, idProductAttribute] = id.split("-");
    return this.lines.filter({
      has: this.page.locator(
        `${DELETE_LINK}[data-id-product="${idProduct}"][data-id-product-attribute="${idProductAttribute}"]`,
      ),
    });
  }

  // Removes a line with its "Usuń" link. The shop deletes it in the background and redraws the cart, so wait
  // until the line is gone and the header count has dropped by its quantity before doing anything else.
  async removeLine(line) {
    const countBefore = Number(await this.headerCount.innerText());
    const row = this.line(line.id);
    await row.locator(DELETE_LINK).click();
    await expect(row, `cart line of ${line.name} after "Usuń"`).toHaveCount(0);
    await expect(this.headerCount, `header cart count after removing ${line.name}`).toHaveText(
      String(countBefore - line.quantity),
    );
  }
}
