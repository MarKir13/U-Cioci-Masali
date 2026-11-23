<?php
/**
 * Product families (issue #114): the rows of tiles above the description that link a product to its siblings,
 * as on the source shop ("Mydło": "100% oliwa", "Czarne eukaliptus", ...).
 *
 * The rows come from data/families.json, a copy of scraper-results/families.json written by
 * `python -m scraper families` (the shop image is built from shop/ only). Shop products are found by
 * `reference`, which the importer sets to the source product ID. A source product that became a combination of
 * another product (deploy/importer/variants.json) is found by the combination's reference, and its tile opens
 * that combination. Which tiles are shown is decided in classes/CiociaFamilyTiles.php.
 *
 * The child theme calls the hook displayCiociaProductFamily from templates/catalog/product.tpl, above the
 * description. Copied into the shop by shop/scripts/sync-code.sh and installed by
 * shop/scripts/setup/configure-shop.php.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

require_once __DIR__ . '/classes/CiociaFamilyTiles.php';

class CiociaFamily extends Module
{
    public const HOOK = 'displayCiociaProductFamily';

    /** @var array|null rows of families.json by source product ID, read once per request */
    private static $families;

    public function __construct()
    {
        $this->name = 'ciociafamily';
        $this->tab = 'front_office_features';
        $this->version = '1.0.0';
        $this->author = 'U Cioci Masali';
        $this->need_instance = 0;
        $this->ps_versions_compliancy = ['min' => '8.0.0', 'max' => _PS_VERSION_];

        parent::__construct();

        $this->displayName = 'Ciocia: rodziny produktów';
        $this->description = 'Kafelki z wariantami produktu (zapach, pojemność...) nad opisem, jak w sklepie źródłowym.';
    }

    public function install()
    {
        return parent::install() && $this->registerHook(self::HOOK);
    }

    public function hookDisplayCiociaProductFamily(array $params)
    {
        $productId = (int) ($params['product']['id_product'] ?? 0);
        // The product's own reference: the one on the page may be the selected combination's
        $sourceId = (int) Db::getInstance()->getValue(
            'SELECT reference FROM `' . _DB_PREFIX_ . 'product` WHERE id_product = ' . $productId
        );
        $rows = self::families()[$sourceId] ?? [];
        if ($rows === []) {
            return '';
        }

        $targets = $this->findProducts(CiociaFamilyTiles::sourceIds($rows));
        $rows = CiociaFamilyTiles::build($rows, $sourceId, $productId, $targets);
        if ($rows === []) {
            return '';
        }

        $link = $this->context->link;
        foreach ($rows as &$row) {
            foreach ($row['tiles'] as &$tile) {
                $target = $tile['target'];
                $tile['name'] = $target['name'];
                // The 7th argument is the combination: its link opens the product with that variant chosen
                $tile['url'] = $link->getProductLink(
                    (int) $target['id_product'], null, null, null, null, null, (int) $target['id_product_attribute']
                );
                $tile['image'] = $row['kind'] === 'image' ? $this->imageUrl($target) : '';
            }
            unset($tile);
        }
        unset($row);

        $this->context->smarty->assign(['ciocia_family' => $rows]);

        return $this->fetch('module:ciociafamily/views/templates/hook/family.tpl');
    }

    /** families.json as an array: source product ID => rows. Empty if the file is missing or broken. */
    private static function families(): array
    {
        if (self::$families === null) {
            $file = __DIR__ . '/data/families.json';
            $data = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;
            self::$families = is_array($data) ? $data : [];
        }

        return self::$families;
    }

    /**
     * Active shop products, or combinations, whose reference is one of these source IDs: source ID =>
     * id_product, id_product_attribute (0 for a product), name, link_rewrite. A product wins over a combination
     * with the same reference (the default variant of a product with variants has both).
     */
    private function findProducts(array $sourceIds): array
    {
        if ($sourceIds === []) {
            return [];
        }
        $references = implode(',', array_map(function ($id) {
            return "'" . (int) $id . "'";
        }, $sourceIds));
        $idShop = (int) $this->context->shop->id;
        $idLang = (int) $this->context->language->id;
        $prefix = _DB_PREFIX_;
        $join = "INNER JOIN `{$prefix}product_shop` ps
                ON ps.id_product = p.id_product AND ps.id_shop = $idShop AND ps.active = 1
            INNER JOIN `{$prefix}product_lang` pl
                ON pl.id_product = p.id_product AND pl.id_shop = $idShop AND pl.id_lang = $idLang";
        $rows = Db::getInstance()->executeS(
            "SELECT p.reference, p.id_product, 0 AS id_product_attribute, pl.name, pl.link_rewrite, 0 AS is_combination
            FROM `{$prefix}product` p
            $join
            WHERE p.reference IN ($references)
            UNION ALL
            SELECT pa.reference, p.id_product, pa.id_product_attribute, pl.name, pl.link_rewrite, 1 AS is_combination
            FROM `{$prefix}product_attribute` pa
            INNER JOIN `{$prefix}product` p ON p.id_product = pa.id_product
            $join
            WHERE pa.reference IN ($references)
            ORDER BY is_combination"
        ) ?: [];

        $targets = [];
        foreach ($rows as $row) {
            $sourceId = (int) $row['reference'];
            if (!isset($targets[$sourceId])) {
                $targets[$sourceId] = $row;
            }
        }

        return $targets;
    }

    /**
     * The photo of the product, or of the combination when it has its own. Empty if there is none. The listing size
     * (home_default, 250 px) stays sharp on high-density screens; small_default (98 px) is blurred there.
     */
    private function imageUrl(array $target): string
    {
        $image = false;
        if ((int) $target['id_product_attribute'] > 0) {
            $image = Product::getCombinationImageById(
                (int) $target['id_product_attribute'],
                (int) $this->context->language->id
            );
        }
        if (empty($image['id_image'])) {
            $image = Product::getCover((int) $target['id_product']);
        }
        if (empty($image['id_image'])) {
            return '';
        }

        return $this->context->link->getImageLink(
            $target['link_rewrite'],
            (int) $image['id_image'],
            ImageType::getFormattedName('home')
        );
    }
}
