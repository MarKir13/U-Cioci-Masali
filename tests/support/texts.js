// Polish texts the tests assert on, kept in one place: a change of wording in the shop is fixed here only.
// They come from PrestaShop's Polish translation (translations/pl-PL in the shop container).
export const texts = {
  checkout: {
    // Fee shown for a carrier when delivery is free (cart from 2000 PLN, shop-settings.php)
    freeShipping: "Za darmo!",
    // Name of the cash on delivery method in the order (module ps_cashondelivery)
    cashOnDelivery: "Płatność przy odbiorze",
  },
  confirmation: {
    title: "Twoje zamówienie zostało potwierdzone",
    // Lines of "Szczegóły zamówienia", each followed by the value
    reference: "Numer zamówienia:",
    payment: "Metoda płatności:",
    carrier: "Sposób dostawy:",
  },
  history: {
    // Status of a new cash on delivery order (PS_OS_COD_VALIDATION). The shop issues the invoice in this
    // status (configureInvoices() in shop/scripts/setup/configure-shop.php), so step 10 can download it.
    cashOnDeliveryStatus: "Oczekiwanie na płatność przy odbiorze",
  },
};
