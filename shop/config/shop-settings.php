<?php
/**
 * Shop settings applied by shop/scripts/setup/configure-shop.php (issue #47).
 *
 * This is the one place to change delivery, payment and e-mail settings. After a change:
 *   docker compose -f deploy/compose.yaml up -d --build
 *   docker compose -f deploy/compose.yaml exec shop runuser -u www-data -- \
 *       php /opt/ciocia/scripts/setup/configure-shop.php
 * A fresh install (after `down -v`) applies it automatically.
 *
 * All amounts are in PLN, gross (VAT included), as the customer sees them.
 */

return [
    // Currencies. PLN is the default; EUR stays in the selector, as on magiczne-indie.pl.
    'currency_default' => 'PLN',
    'currencies_extra' => [
        'EUR' => 0.23, // fixed exchange rate: 1 PLN = 0.23 EUR (no live rate download)
    ],

    // Country used by default in address forms
    'country_default' => 'PL',

    // Free delivery when the cart (products, gross, after discounts) reaches this amount
    'free_shipping_from' => 2000,

    // VAT rate on delivery fees, in %. Fees below are gross; the script stores them net.
    'shipping_vat' => 23,

    // Carriers. A cart heavier than the last range has no delivery option.
    // 'ranges' maps "up to N kg" => gross fee in PLN; ranges start where the previous one ends.
    'carriers' => [
        'Kurier' => [
            'delay' => 'Dostawa w 1-2 dni robocze',
            'ranges' => [5 => 16.99, 10 => 19.99, 20 => 24.99, 30 => 29.99, 50 => 39.99],
        ],
        'Paczkomat' => [
            'delay' => 'Odbiór w automacie paczkowym w 1-2 dni robocze',
            'ranges' => [5 => 12.99, 10 => 14.99, 20 => 18.99, 30 => 22.99, 50 => 29.99],
        ],
    ],

    // Bank transfer details shown to the customer. FICTIONAL: not a real account or company.
    'bank_wire' => [
        'owner' => 'U Cioci Masali sp. z o.o. (firma fikcyjna, projekt studencki)',
        'details' => 'PL00 0000 0000 0000 0000 0000 0000 (numer fikcyjny, nie wpłacaj pieniędzy)',
        'address' => 'ul. Przykładowa 1, 80-000 Gdańsk',
    ],

    // Outgoing e-mail: SMTP to the Mailpit container from deploy/compose.yaml
    'mail' => [
        'server' => 'mailpit',
        'port' => 1025,
    ],
];
