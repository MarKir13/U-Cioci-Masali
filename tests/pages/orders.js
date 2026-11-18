import { expect } from "../support/fixtures.js";

// Order history of a logged-in customer: header → "Moje konto" → "Historia i szczegóły zamówień".
// The ciocia theme keeps Classic's customer/history.tpl, which prints every order twice: as a table row on
// wider screens and as a card on phones. The test runs at desktop width, so it reads the table only.
export class OrdersPage {
  constructor(page) {
    this.page = page;
    // Header account icon of a logged-in customer (shop/themes/ciocia/modules/ps_customersignin)
    this.headerAccountLink = page.locator("#_desktop_user_info .user-info a.account");
    this.historyLink = page.locator("#history-link");
    this.rows = page.locator("#content table tbody tr");
  }

  // The shop's own links, no typed URL
  async openFromHeader() {
    await this.headerAccountLink.click();
    await expect(this.page.locator("body#my-account")).toBeVisible();
    await this.historyLink.click();
    await expect(this.page.locator("body#history")).toBeVisible();
  }

  // The table row of one order; its reference is the row header (<th scope="row">)
  row(reference) {
    return this.rows.filter({
      has: this.page.locator('th[scope="row"]', { hasText: new RegExp(`^\\s*${reference}\\s*$`) }),
    });
  }

  // Columns of the order's row as the customer sees them, plus the invoice link (null without an invoice)
  async readOrder(reference) {
    const row = this.row(reference);
    await expect(row, `order ${reference} in the order history`).toHaveCount(1);
    // td 0: date, 1: total, 2: payment, 3: status, 4: invoice, 5: details
    const cells = row.locator("td");
    const invoiceLink = cells.nth(4).locator("a");
    // textContent, not innerText: Classic hides the payment and invoice columns below 992 px (hidden-md-down)
    return {
      payment: (await cells.nth(2).textContent()).trim(),
      status: (await cells.nth(3).textContent()).trim(),
      invoiceUrl: (await invoiceLink.count()) ? await invoiceLink.getAttribute("href") : null,
    };
  }
}
