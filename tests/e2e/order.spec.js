import { test } from "../support/fixtures.js";

// The W4 scenario is one test: every step needs what the previous one left (cart, customer, order).
// Issues E2E 2/5 to 5/5 replace each test.step.skip with the real step.
test("W4: from an empty cart to the VAT invoice", async () => {
  await test.step.skip("1. Add 10 products in varying quantities from 2 categories to the cart", async () => {});
  await test.step.skip("2. Search by name and add a random result to the cart", async () => {});
  await test.step.skip("3. Remove 3 products from the cart", async () => {});
  await test.step.skip("4. Register a new account", async () => {});
  await test.step.skip("5. Order the cart contents", async () => {});
  await test.step.skip("6. Choose cash on delivery", async () => {});
  await test.step.skip("7. Choose one of the two new carriers", async () => {});
  await test.step.skip("8. Confirm the order", async () => {});
  await test.step.skip("9. Check the order status", async () => {});
  await test.step.skip("10. Download the VAT invoice", async () => {});
});