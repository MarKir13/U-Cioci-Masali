import { test, expect } from "../support/fixtures.js";
import { AccountPage } from "../pages/account.js";
import { cartSnapshot } from "../support/cart-state.js";
import { newCustomer } from "../support/data.js";
import { mailpitUrl, messagesTo } from "../support/mailpit.js";

// The W4 scenario is one test: every step needs what the previous one left (cart, customer, order).
// Issues E2E 2/5 to 5/5 replace each test.step.skip with the real step.
test("W4: from an empty cart to the VAT invoice", async ({ page, request }) => {
  await test.step.skip("1. Add 10 products in varying quantities from 2 categories to the cart", async () => {});
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
