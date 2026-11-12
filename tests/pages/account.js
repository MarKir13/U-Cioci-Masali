import { expect } from "../support/fixtures.js";

// Customer account: registration from the header and the logged-in state.
// Selectors rely on PrestaShop's field names and data-link-action attributes, which both Classic and
// the ciocia templates keep, so a change of the look does not break the test.
export class AccountPage {
  constructor(page) {
    this.page = page;
    // Header account icon (shop/themes/ciocia/modules/ps_customersignin): a log-in link for a guest,
    // a link to "Moje konto" (class "account") for a logged-in customer
    this.headerUserInfo = page.locator("#_desktop_user_info .user-info");
    this.headerLoginLink = this.headerUserInfo.locator("a:not(.account)");
    this.headerAccountLink = this.headerUserInfo.locator("a.account");
    // "Nie masz konta?" on the log-in page
    this.createAccountLink = page.locator('#main a[data-link-action="display-register-form"]');
    this.form = page.locator("#customer-form");
    this.submitButton = this.form.locator('button[data-link-action="save-customer"]');
  }

  // Header icon → log-in page → registration form. The shop's own links, no typed URL.
  async openRegistrationFromHeader() {
    await this.headerLoginLink.click();
    await expect(this.page.locator("body#authentication")).toBeVisible();
    await this.createAccountLink.click();
    await expect(this.page.locator("body#registration")).toBeVisible();
    await expect(this.form).toBeVisible();
  }

  async register(customer) {
    await this.form.locator('input[name="firstname"]').fill(customer.firstName);
    await this.form.locator('input[name="lastname"]').fill(customer.lastName);
    await this.form.locator('input[name="email"]').fill(customer.email);
    await this.form.locator('input[name="password"]').fill(customer.password);
    // Every consent marked required (terms, privacy notice); optional ones such as the newsletter stay unticked
    const requiredBoxes = await this.form.locator('input[type="checkbox"][required]').all();
    expect(requiredBoxes.length, "the form should ask for at least one required consent").toBeGreaterThan(0);
    for (const box of requiredBoxes) {
      await box.check();
    }
    await this.submitButton.click();
    // After a successful registration PrestaShop leaves the form page; on an error it shows the form again
    await this.page.waitForURL((url) => !url.pathname.includes("rejestracja"));
  }

  // The customer the shop thinks is logged in, from PrestaShop's own front-end object
  async loggedInCustomer() {
    return this.page.evaluate(() => {
      const { is_logged: isLogged, email, firstname, lastname } = globalThis.prestashop.customer;
      return { isLogged, email, firstName: firstname, lastName: lastname };
    });
  }
}
