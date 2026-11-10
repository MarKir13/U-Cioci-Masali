<?php
// Shop details, delivery and payment values, kept in one place.
//
// shop-content.php uses them for the store details and for the text of the "Dostawa" and
// "Formy płatności" pages. The shop configuration script (#47) is meant to set carriers, fees and
// payments from the same values, so one change here (for example the free delivery threshold)
// reaches both the configuration and the pages that describe it.
//
// Everything here is fictional: no real company, address, e-mail or bank account.

return [
    'shop' => [
        'name' => 'U Cioci Masali',
        'address1' => 'ul. Przykładowa 1',
        'postcode' => '80-001',
        'city' => 'Gdańsk',
        'country_iso' => 'PL',
        'email' => 'kontakt@example.com',
    ],

    'delivery' => [
        // Carts worth this much or more (PLN, gross) ship for free.
        'free_from' => 2000,
        // Heavier carts cannot be delivered.
        'max_weight_kg' => 50,
        // Gross fee in PLN.
        'carriers' => [
            ['name' => 'Kurier', 'fee' => 19.99, 'time' => '1–2 dni robocze'],
            ['name' => 'Odbiór w punkcie', 'fee' => 12.99, 'time' => '2–3 dni robocze'],
        ],
    ],

    'bank_transfer' => [
        'owner' => 'U Cioci Masali',
        'bank' => 'Bank Przykładowy',
        // Check digits 00 are never valid, so this cannot be a real account.
        'account' => 'PL00 0000 0000 0000 0000 0000 0000',
    ],
];
