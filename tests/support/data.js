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

// Fictional Polish address; the postcode has the NN-NNN format. The shop requires the phone
// (address_required_fields in shop/config/shop-settings.php).
export const testAddress = {
  address1: "ul. Grunwaldzka 2137",
  postcode: "80-233",
  city: "Gdańsk",
  country: "Polska",
  phone: "500100200",
};

// The two carriers added by shop/config/shop-settings.php (W3). The test never uses a demo carrier.
export const newCarriers = ["Kurier", "Paczkomat"];

// Carrier for this run: E2E_CARRIER if set, otherwise picked with the run's seed
export function chooseCarrier(rng) {
  const wanted = process.env.E2E_CARRIER || rng.pick(newCarriers);
  if (!newCarriers.includes(wanted)) {
    throw new Error(`E2E_CARRIER must be one of ${newCarriers.join(", ")}, got "${wanted}"`);
  }
  return wanted;
}
