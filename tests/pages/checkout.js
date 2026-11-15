import { expect } from "../support/fixtures.js";
import { toGrosze } from "../support/price.js";
import { texts } from "../support/texts.js";

// Delivery fee in grosze from a text such as "16,99 zł brutto", 0 for free delivery, null if neither
function deliveryFee(text) {
  return text.includes(texts.checkout.freeShipping) ? 0 : toGrosze(text);
}

// First line of a detail after its label: "Sposób dostawy: Kurier\nDostawa w 1-2 dni" → "Kurier"
function detailValue(text, label) {
  return text.split(label)[1].trim().split("\n")[0].trim();
}

// Checkout of a logged-in customer: cart → address → carrier → payment → order confirmation.
// Selectors rely on PrestaShop's ids, field names and data-module-name attributes, which both Classic and
// the ciocia templates keep, so a change of the look does not break the test.
export class CheckoutPage {
  constructor(page) {
    this.page = page;
    // Cart page: "Przejdź do realizacji zamówienia"
    this.proceedButton = page.locator(".cart-detailed-actions a.btn-primary");

    // Each step is a <section> that gets the class -complete once done and -current while open
    this.addressStep = page.locator("#checkout-addresses-step");
    this.deliveryStep = page.locator("#checkout-delivery-step");
    this.paymentStep = page.locator("#checkout-payment-step");

    this.addressForm = this.addressStep.locator(".js-address-form form");
    this.deliveryOptions = page.locator("#js-delivery .js-delivery-option");
    this.paymentOptions = page.locator('input[name="payment-option"]');
    this.termsBoxes = page.locator('#conditions-to-approve input[type="checkbox"]');
    this.placeOrderButton = page.locator("#payment-confirmation button[type=submit]");

    // Summary next to the steps, refreshed by the shop after every change
    this.summaryShipping = page.locator("#js-checkout-summary #cart-subtotal-shipping .value");
    // "Razem (brutto)": the amount the customer agrees to pay
    this.summaryTotal = page.locator("#js-checkout-summary .cart-summary-totals .cart-total .value");

    this.orderDetails = page.locator("#order-details");
    // Errors the shop shows when it rejects a form or the order
    this.errors = page.locator(".js-address-form .help-block li, #notifications .alert-danger");
  }

  // Step 5 starts here: from the cart page, with the shop's own button
  async openFromCart() {
    const cartUrl = await this.page.evaluate(() => globalThis.prestashop.urls.pages.cart);
    await this.page.goto(`${cartUrl}?action=show`);
    await expect(this.page.locator("body#cart")).toBeVisible();
    await this.proceedButton.click();
    await expect(this.page.locator("body#checkout")).toBeVisible();
  }

  // A new customer has no address yet, so the shop shows the address form
  async fillAddress(address) {
    await expect(this.addressStep).toHaveClass(/-current/);
    const form = this.addressForm;
    await form.locator('input[name="address1"]').fill(address.address1);
    await form.locator('input[name="postcode"]').fill(address.postcode);
    await form.locator('input[name="city"]').fill(address.city);
    // Required by the shop (address_required_fields in shop-settings.php): the carriers need it
    await form.locator('input[name="phone"]').fill(address.phone);
    // Only Poland is active (shop-settings.php), so the country is preselected; check it, do not change it
    await expect(form.locator('select[name="id_country"] option:checked')).toHaveText(address.country);
    // Polish address format: no state field
    await expect(form.locator('[name="id_state"]')).toHaveCount(0);
    // A required field left empty stops the browser from sending the form, with no message from the shop,
    // so name such fields here instead of waiting for a step that never comes
    const invalid = await form.locator("input:invalid, select:invalid").evaluateAll((fields) => fields.map((f) => f.name));
    expect(invalid, "required address fields left empty").toEqual([]);
    await form.locator('button[name="confirm-addresses"]').click();
    // Wait for the next step or for an error, so a rejected address fails at once with the shop's message
    await expect(this.deliveryStep.and(this.page.locator(".-current")).or(this.errors).first()).toBeVisible();
    expect(await this.errors.allInnerTexts(), "the shop rejected the address").toEqual([]);
    await expect(this.addressStep).toHaveClass(/-complete/);
  }

  // Names of the carriers offered, in the order shown
  async carrierNames() {
    await expect(this.deliveryStep).toHaveClass(/-current/);
    return this.deliveryOptions.locator(".carrier-name").allInnerTexts();
  }

  // Chooses the carrier and returns its fee in grosze (0 for free delivery)
  async chooseCarrier(name) {
    const option = this.deliveryOptions.filter({
      has: this.page.locator(".carrier-name", { hasText: new RegExp(`^\\s*${name}\\s*$`) }),
    });
    await expect(option).toHaveCount(1);
    await option.locator("label").click();
    await expect(option.locator('input[type="radio"]')).toBeChecked();

    const priceText = await option.locator(".carrier-price").innerText();
    const fee = deliveryFee(priceText);
    expect(fee, `fee of ${name}: "${priceText}"`).not.toBeNull();
    // The shop saves the choice with an AJAX request and redraws the summary; wait for the same fee there
    await expect
      .poll(async () => deliveryFee(await this.summaryShipping.innerText()), { message: "delivery fee in the summary" })
      .toBe(fee);

    await this.deliveryStep.locator('button[name="confirmDeliveryOption"]').click();
    await expect(this.deliveryStep).toHaveClass(/-complete/);
    await expect(this.paymentStep).toHaveClass(/-current/);
    return fee;
  }

  // Module names of the payment methods offered (data-module-name)
  async paymentModules() {
    await expect(this.paymentOptions.first()).toBeAttached();
    return this.paymentOptions.evaluateAll((inputs) => inputs.map((input) => input.dataset.moduleName));
  }

  async choosePayment(moduleName) {
    const option = this.page.locator(`input[name="payment-option"][data-module-name="${moduleName}"]`);
    const id = await option.getAttribute("id");
    await this.page.locator(`label[for="${id}"]`).click();
    await expect(option).toBeChecked();
  }

  // Total of the checkout summary in grosze. Read it after chooseCarrier(), which waits for the summary to
  // show the new delivery fee, so the total includes it too.
  async summaryTotalGrosze() {
    return toGrosze(await this.summaryTotal.innerText());
  }

  // Accepts every condition the shop asks for (terms of service) and places the order
  async placeOrder() {
    const boxes = await this.termsBoxes.all();
    expect(boxes.length, "the shop should ask to accept the terms").toBeGreaterThan(0);
    for (const box of boxes) {
      await box.check();
    }
    await expect(this.placeOrderButton).toBeEnabled();
    await this.placeOrderButton.click();
    await expect(this.page.locator("body#order-confirmation").or(this.errors).first()).toBeVisible();
    expect(await this.errors.allInnerTexts(), "the shop rejected the order").toEqual([]);
  }

  // Order reference, from its own line (#order-reference-value) that starts with "Numer zamówienia:"
  async orderReference() {
    const line = this.orderDetails.locator("#order-reference-value");
    await expect(line).toContainText(texts.confirmation.reference);
    return detailValue(await line.innerText(), texts.confirmation.reference);
  }

  // Text after "<label>" in the order details, such as the carrier after "Sposób dostawy:".
  // These lines have no id in the template, so they are found by their label.
  async orderDetail(label) {
    const line = this.orderDetails.locator("li", { hasText: label });
    await expect(line).toHaveCount(1);
    return detailValue(await line.innerText(), label);
  }

  // Order total in grosze, from the row the template marks as the total (tr.total-value),
  // and every row of the totals table as text, for the failure message
  async confirmationTotals() {
    const table = this.page.locator(".order-confirmation-table table");
    const totalRow = table.locator("tr.total-value");
    await expect(totalRow).toHaveCount(1);
    return {
      total: toGrosze(await totalRow.locator("td").last().innerText()),
      rows: await table.locator("tr").allInnerTexts(),
    };
  }
}
