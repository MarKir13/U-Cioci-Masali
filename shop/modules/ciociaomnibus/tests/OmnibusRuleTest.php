<?php
/**
 * Test of the Omnibus rule (classes/CiociaOmnibusRule.php), without PrestaShop or a database.
 * Run from the repository root:
 *   docker run --rm -v "$PWD:/repo:ro" -w /repo php:8.1.34-cli php shop/modules/ciociaomnibus/tests/OmnibusRuleTest.php
 * Exits with 1 if any case fails, which fails the CI step.
 */
if (PHP_SAPI !== 'cli') {
    // The module folder is inside the web root, so do not run from a browser
    exit(1);
}

define('_PS_VERSION_', 'test');
require __DIR__ . '/../classes/CiociaOmnibusRule.php';

/** One row of the price history, as the module reads it from ciocia_price_history. */
function row(string $date, float $price): array
{
    return ['date_add' => $date, 'price_gross' => $price];
}

$promoStart = new DateTimeImmutable('2026-11-01 12:00:00');
$regularPrice = 30.00;

$cases = [
    'price changed twice within 30 days: the lower one counts' => [
        [
            row('2026-09-01 10:00:00', 30.00),
            row('2026-10-10 08:00:00', 22.00),
            row('2026-10-20 08:00:00', 30.00),
            // the promotion price, saved by the hook half a millisecond after the start: not counted,
            // otherwise the line would show the promotion price itself
            row('2026-11-01 12:00:00.000500', 20.00),
        ],
        22.00,
    ],
    'promotion without any history: the regular price' => [
        [],
        30.00,
    ],
    'price set before the window and still in effect when it opened' => [
        [
            row('2026-09-01 10:00:00', 19.99),
            row('2026-10-15 08:00:00', 25.00),
        ],
        19.99,
    ],
    'price replaced before the window opened: not counted' => [
        [
            row('2026-08-01 10:00:00', 10.00),
            row('2026-09-01 10:00:00', 30.00),
        ],
        30.00,
    ],
    'history only from the promotion start on: the regular price' => [
        [
            row('2026-11-01 12:00:00', 27.00),
            row('2026-11-05 09:00:00', 26.00),
        ],
        30.00,
    ],
];

$failed = 0;
foreach ($cases as $name => [$history, $expected]) {
    $actual = CiociaOmnibusRule::lowestPrice($history, $promoStart, $regularPrice);
    if (abs($actual - $expected) < 0.000001) {
        echo "ok   $name\n";
    } else {
        echo "FAIL $name: expected $expected, got $actual\n";
        ++$failed;
    }
}

echo $failed === 0 ? 'All ' . count($cases) . " cases passed\n" : "$failed case(s) failed\n";
exit($failed === 0 ? 0 : 1);
