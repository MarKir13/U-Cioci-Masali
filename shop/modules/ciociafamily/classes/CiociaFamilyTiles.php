<?php
/**
 * Which family tiles a product page shows (issue #114).
 *
 * Plain PHP without PrestaShop classes or the database, so tests/FamilyTilesTest.php can run it on its own.
 * The module reads the product's rows from data/families.json, finds the shop products of the source IDs
 * (by reference) and passes both here.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class CiociaFamilyTiles
{
    /** Source IDs of every tile in the rows, to look them all up in one query. */
    public static function sourceIds(array $rows): array
    {
        $ids = [];
        foreach ($rows as $row) {
            foreach ($row['options'] as $option) {
                $ids[(int) $option['source_id']] = true;
            }
        }

        return array_keys($ids);
    }

    /**
     * The rows to show, each with its tiles in the source's order:
     * - the tile of the page's own source product is the current one (highlighted, not a link);
     * - a tile whose source product is not in the shop is left out (a subset import, or a product
     *   the importer rejected);
     * - a tile that leads to the page's own product is left out: it is a variant of this product
     *   (deploy/importer/variants.json), already offered by the variant selector;
     * - a row left with fewer than 2 tiles is not shown, since there is nothing to choose from.
     *
     * @param array $rows rows of families.json: ['title' => ?string, 'kind' => 'image'|'text', 'options' => [...]]
     * @param int $currentSourceId source ID of the page's product (its reference)
     * @param int $currentProductId the page's id_product
     * @param array $targets source ID => ['id_product' => int, ...], only for the source IDs found in the shop
     */
    public static function build(array $rows, int $currentSourceId, int $currentProductId, array $targets): array
    {
        $result = [];
        foreach ($rows as $row) {
            $tiles = [];
            foreach ($row['options'] as $option) {
                $sourceId = (int) $option['source_id'];
                $current = $sourceId === $currentSourceId;
                if (!isset($targets[$sourceId])) {
                    continue;
                }
                if (!$current && (int) $targets[$sourceId]['id_product'] === $currentProductId) {
                    continue;
                }
                $tiles[] = [
                    'label' => (string) $option['label'],
                    'current' => $current,
                    'target' => $targets[$sourceId],
                ];
            }
            if (count($tiles) >= 2) {
                $result[] = ['title' => $row['title'], 'kind' => $row['kind'], 'tiles' => $tiles];
            }
        }

        return $result;
    }
}
