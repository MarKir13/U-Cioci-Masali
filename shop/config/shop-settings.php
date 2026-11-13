<?php
/**
 * Shop settings, read by two setup scripts, run in this order by shop/scripts/post-install/:
 * - 20-shop-content.sh (shop-content.php, issue #27) writes the store details and fills the CMS pages
 *   "Dostawa", "Formy płatności", "Regulamin" and others with the same values, so the pages always
 *   describe what the checkout really offers;
 * - 30-configure-shop.sh (configure-shop.php, issue #47) applies them to the shop configuration.
 *
 * This is the one place to change store details, delivery, payment and e-mail settings and the home page
 * banner. After a change
 * (Git Bash: prefix the exec commands with MSYS_NO_PATHCONV=1):
 *   docker compose -f deploy/compose.yaml up -d --build
 *   docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/20-shop-content.sh
 *   docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/30-configure-shop.sh
 * A fresh install (after `down -v`) applies it automatically.
 *
 * All amounts are in PLN, gross (VAT included), as the customer sees them.
 */

return [
    // Store details: footer, contact page, sender of shop e-mails and the CMS pages.
    // FICTIONAL: no real company, address or e-mail.
    'store' => [
        'name' => 'U Cioci Masali',
        'address1' => 'ul. Przykładowa 1',
        'postcode' => '80-000',
        'city' => 'Gdańsk',
        'country_iso' => 'PL',
        'email' => 'kontakt@example.com',
    ],

    // Currencies. PLN is the default; EUR stays in the selector, as on magiczne-indie.pl.
    // Both payment methods accept every currency listed here.
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

    // Bank transfer details shown to the customer (also on the "Formy płatności" page).
    // FICTIONAL: not a real account or company.
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

    // Home page banner (issue #63): image slider on the left, text and two buttons on the right, as on
    // magiczne-indie.pl. Applied by 20-shop-content.sh. Template: themes/ciocia/modules/ps_imageslider/.
    'home_banner' => [
        'eyebrow' => 'Magiczne Indie od 2010 roku', // small line above the title, shown in capitals
        'title' => 'Sklep ajurwedyjski - kosmetyki i suplementy z Indii',
        'lead' => 'Dawny sklep stacjonarny stworzyliśmy z miłości do Ajurwedy. Dziś jego atmosferę '
            . 'i starannie wybraną ofertę przenosimy do zakupów online.',
        // 'link' is a PrestaShop page name ('new-products', 'prices-drop', 'best-sales', 'contact', ...)
        // or a category ID, for example 'link' => 3 (or '3'). The categories come with the data
        // import; until then the buttons lead to product list pages that already exist.
        'button_primary' => ['label' => 'Odkryj kosmetyki', 'link' => 'new-products'],
        'button_secondary' => ['label' => 'Zobacz suplementy', 'link' => 'prices-drop'],
        // Slides in order. Files are in shop/themes/ciocia/assets/img/home-banner/; 'alt' describes the
        // photo for screen readers. Adding or removing a line adds or removes a slide.
        'slides' => [
            ['image' => 'mi-slide-1.jpg', 'alt' => 'Wnętrze sklepu stacjonarnego Magiczne Indie'],
            ['image' => 'mi-slide-2.jpg', 'alt' => 'Półki z suplementami w sklepie Magiczne Indie'],
        ],
    ],
];
