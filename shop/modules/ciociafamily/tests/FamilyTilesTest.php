<?php
/**
 * Test of the family tile rules (classes/CiociaFamilyTiles.php), without PrestaShop or a database.
 * Run from the repository root:
 *   docker run --rm -v "$PWD:/repo:ro" -w /repo php:8.1.34-cli php shop/modules/ciociafamily/tests/FamilyTilesTest.php
 * Exits with 1 if any case fails, which fails the CI step.
 */
if (PHP_SAPI !== 'cli') {
    // The module folder is inside the web root, so do not run from a browser
    exit(1);
}

define('_PS_VERSION_', 'test');
require __DIR__ . '/../classes/CiociaFamilyTiles.php';

/** A row of families.json; $options are source ID => label. */
function row(?string $title, array $options, string $kind = 'image'): array
{
    $list = [];
    foreach ($options as $id => $label) {
        $list[] = ['source_id' => $id, 'label' => $label];
    }

    return ['title' => $title, 'kind' => $kind, 'options' => $list];
}

/** What the module found in the shop: source ID => id_product (and the combination, 0 for a product). */
function targets(array $products): array
{
    $targets = [];
    foreach ($products as $sourceId => [$idProduct, $idAttribute]) {
        $targets[$sourceId] = ['id_product' => $idProduct, 'id_product_attribute' => $idAttribute];
    }

    return $targets;
}

/** The result in short: title => labels, the current one in brackets. */
function shown(array $rows): array
{
    $result = [];
    foreach ($rows as $row) {
        $result[(string) $row['title']] = array_map(function ($tile) {
            return $tile['current'] ? '[' . $tile['label'] . ']' : $tile['label'];
        }, $row['tiles']);
    }

    return $result;
}

$soaps = row('Mydło', [2858 => '100% oliwa', 3715 => 'Czarne eukaliptus', 1484 => 'Czarnuszka']);

$cases = [
    'every sibling in the shop: all tiles, the page\'s own highlighted' => [
        [$soaps], 3715, 10, targets([2858 => [11, 0], 3715 => [10, 0], 1484 => [12, 0]]),
        ['Mydło' => ['100% oliwa', '[Czarne eukaliptus]', 'Czarnuszka']],
    ],
    'a sibling missing from the shop is left out' => [
        [$soaps], 3715, 10, targets([3715 => [10, 0], 1484 => [12, 0]]),
        ['Mydło' => ['[Czarne eukaliptus]', 'Czarnuszka']],
    ],
    'a row with one tile left is not shown' => [
        [$soaps], 3715, 10, targets([3715 => [10, 0]]),
        [],
    ],
    'a variant of the page\'s own product is left out (the variant selector offers it)' => [
        [row('Pojemność', [7392 => '50 ml', 120 => '150 ml'], 'text'), $soaps],
        7392, 20, targets([7392 => [20, 0], 120 => [20, 5], 2858 => [11, 0], 1484 => [12, 0]]),
        // Pojemność has one tile left; the soap row has no current tile but still two siblings
        ['Mydło' => ['100% oliwa', 'Czarnuszka']],
    ],
    'a sibling that is a combination of another product is kept and points at that combination' => [
        [row('Pojemność', [5212 => '75 g', 5211 => '150 g', 9000 => '300 g'], 'text')],
        9000, 30, targets([5212 => [40, 0], 5211 => [40, 7], 9000 => [30, 0]]),
        ['Pojemność' => ['75 g', '150 g', '[300 g]']],
    ],
    'a row without a title keeps its tiles' => [
        [row(null, [5031 => 'Palo Santo', 5032 => 'Palo Santo I'])], 5031, 50, targets([5031 => [50, 0], 5032 => [51, 0]]),
        ['' => ['[Palo Santo]', 'Palo Santo I']],
    ],
];

$failed = 0;
foreach ($cases as $name => [$rows, $currentSource, $currentProduct, $found, $expected]) {
    $actual = shown(CiociaFamilyTiles::build($rows, $currentSource, $currentProduct, $found));
    if ($actual === $expected) {
        echo "ok   $name\n";
    } else {
        echo "FAIL $name: expected " . json_encode($expected, JSON_UNESCAPED_UNICODE)
            . ', got ' . json_encode($actual, JSON_UNESCAPED_UNICODE) . "\n";
        ++$failed;
    }
}

// The combination's link needs its id_product_attribute
$rows = CiociaFamilyTiles::build(
    [row('Pojemność', [5212 => '75 g', 5211 => '150 g', 9000 => '300 g'], 'text')],
    9000, 30, targets([5212 => [40, 0], 5211 => [40, 7], 9000 => [30, 0]])
);
if ($rows[0]['tiles'][1]['target']['id_product_attribute'] === 7) {
    echo "ok   the combination tile keeps its id_product_attribute\n";
} else {
    echo "FAIL the combination tile lost its id_product_attribute\n";
    ++$failed;
}

if (CiociaFamilyTiles::sourceIds([$soaps, row('X', [2858 => 'a', 9 => 'b'])]) === [2858, 3715, 1484, 9]) {
    echo "ok   source IDs are listed once each\n";
} else {
    echo "FAIL source IDs\n";
    ++$failed;
}

echo $failed === 0 ? "All cases passed\n" : "$failed case(s) failed\n";
exit($failed === 0 ? 0 : 1);
