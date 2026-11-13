import { test, expect } from "../support/fixtures.js";
import { AccountPage } from "../pages/account.js";
import { CheckoutPage } from "../pages/checkout.js";
import { cartSnapshot } from "../support/cart-state.js";
import { chooseCarrier, newCarriers, newCustomer, testAddress } from "../support/data.js";
import { mailpitUrl, messagesTo } from "../support/mailpit.js";
import { texts } from "../support/texts.js";
import { addFirstHomeProductToCart } from "../support/temp-cart.js";

// The W4 scenario is one test: every step needs what the previous one left (cart, customer, order).
// Issues E2E 2/5 to 5/5 replace each test.step.skip with the real step.
test("W4: from an empty cart to the VAT invoice", async ({ page, request, rng, consoleErrors }) => {
  await test.step.skip("1. Add 10 products in varying quantities from 2 categories to the cart", async () => {});
  await test.step.skip("2. Search by name and add a random result to the cart", async () => {});
  await test.step.skip("3. Remove 3 products from the cart", async () => {});

  // TEMPORARY until steps 1–3 land (issue #52): one product in the cart, so steps 5–8 have something to order
  await addFirstHomeProductToCart(page);

  // Step 8 looks for the order e-mail to this address; steps 9–10 log in again with it
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

  const checkout = new CheckoutPage(page);
  const carrier = chooseCarrier(rng);
  test.info().annotations.push({ type: "carrier", description: carrier });
  // Errors from here on count for "no console errors during checkout"
  const errorsBeforeCheckout = consoleErrors.length;

  // Products total in grosze, from the cart the shop is about to order
  const productsTotal = await test.step("5. Order the cart contents", async () => {
    await checkout.openFromCart();
    const cart = await page.evaluate(() => globalThis.prestashop.cart);
    expect(Number(cart.products_count), "products in the cart").toBeGreaterThan(0);
    // The logged-in customer skips "Dane osobowe" and starts at the address
    await expect(page.locator("#checkout-personal-information-step")).toHaveClass(/-complete/);
    await checkout.fillAddress(testAddress);
    return Math.round(Number(cart.subtotals.products.amount) * 100);
  });

  // The checkout asks for the carrier before the payment, so step 7 runs before step 6
  const shippingFee = await test.step("7. Choose one of the two new carriers", async () => {
    expect((await checkout.carrierNames()).sort(), "carriers offered").toEqual([...newCarriers].sort());
    const fee = await checkout.chooseCarrier(carrier);
    // Free delivery from 2000 PLN (shop-settings.php), otherwise the carrier's fee by weight
    if (productsTotal >= 2000_00) {
      expect(fee, "delivery from 2000 PLN is free").toBe(0);
    } else {
      expect(fee, "delivery below 2000 PLN is paid").toBeGreaterThan(0);
    }
    return fee;
  });

  await test.step("6. Choose cash on delivery", async () => {
    const modules = await checkout.paymentModules();
    expect(modules).toContain("ps_cashondelivery");
    // Cheque is not used in Poland, so the shop must not offer it
    expect(modules).not.toContain("ps_checkpayment");
    await checkout.choosePayment("ps_cashondelivery");
  });

  // Steps 9–10 look this order up in the customer's order history
  // eslint-disable-next-line no-unused-vars -- used by steps 9–10 (E2E 5/5)
  const orderReference = await test.step("8. Confirm the order", async () => {
    await checkout.placeOrder();
    await expect(page.locator("#content-hook_order_confirmation")).toContainText(texts.confirmation.title);

    const reference = await checkout.orderDetail(texts.confirmation.reference);
    expect(reference, "order reference").toMatch(/^[A-Z]{9}$/);
    expect(await checkout.orderDetail(texts.confirmation.payment)).toBe(texts.checkout.cashOnDelivery);
    expect(await checkout.orderDetail(texts.confirmation.carrier)).toBe(carrier);

    const totals = await checkout.confirmationTotals();
    expect(totals.total, `order total (${JSON.stringify(totals.lines)})`).toBe(productsTotal + shippingFee);

    expect(consoleErrors.slice(errorsBeforeCheckout), "console errors during checkout").toEqual([]);

    if (mailpitUrl) {
      await test.step("Order confirmation e-mail arrives in Mailpit", async () => {
        await expect
          .poll(async () => (await messagesTo(request, customer.email, reference)).length, {
            message: `no e-mail with order ${reference} to ${customer.email} in Mailpit (${mailpitUrl})`,
            timeout: 15_000,
          })
          .toBeGreaterThan(0);
      });
    }
    return reference;
  });

  await test.step.skip("9. Check the order status", async () => {});
  await test.step.skip("10. Download the VAT invoice", async () => {});
});
