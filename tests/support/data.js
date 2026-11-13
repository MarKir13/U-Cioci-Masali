import { randomBytes } from "node:crypto";

// Test values only. example.com is reserved for examples (RFC 2606), so nobody gets these e-mails.
// Not taken from the seed: a run repeated with the same E2E_SEED must still register a new customer.
export function newCustomer() {
  const suffix = `${Date.now()}-${randomBytes(3).toString("hex")}`;
  return {
    // Polish letters check that the shop stores and shows them correctly (W3, Polish characters)
    firstName: "Łucja",
    lastName: "Żółkiewska",
    email: `e2e-${suffix}@example.com`,
    // Generated per run: no password in the repository, and strong enough for PrestaShop's password policy
    password: `E2e-${randomBytes(12).toString("base64url")}`,
  };
}

// Fictional Polish address; the postcode has the NN-NNN format
export const testAddress = {
  address1: "ul. Grunwaldzka 2137",
  postcode: "80-233",
  city: "Gdańsk",
  country: "Polska",
};