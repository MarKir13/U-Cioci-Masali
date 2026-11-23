<?php
/**
 * Omnibus price (issue #72): shows "Najniższa cena z 30 dni przed obniżką" for products in a promotion.
 *
 * PrestaShop 8.2.8 does not show this price by itself, so the module keeps its own price history:
 * - ciocia_price_history: the gross price a customer paid for a product (and combination) from a given moment,
 *   one row each time that price changes;
 * - ciocia_promo_start: when a promotion started, for promotions saved without a "from" date;
 * - ciocia_promo_end: the end date of the source's promotion, only shown on cards and the product page (#111,
 *   classes/CiociaPromoEnd.php). The importer writes it through the Webservice API.
 *
 * The module also prints the unit price of the product page ("100g = 12.37 zł", type 'ciocia_unit_price'),
 * because both lines hang on the same hook of the price block.
 *
 * Copied into the shop by shop/scripts/sync-code.sh and installed by shop/scripts/setup/configure-shop.php.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

require_once __DIR__ . '/classes/CiociaOmnibusRule.php';
require_once __DIR__ . '/classes/CiociaPriceHistory.php';
require_once __DIR__ . '/classes/CiociaPromoEnd.php';

class CiociaOmnibus extends Module
{
    /**
     * Hooks used by the module. Object hooks are named actionObject<Class><Action>After and run for every save
     * through PrestaShop's classes: the back office, the Webservice API (our import) and the setup scripts.
     * displayProductPriceBlock shows the Omnibus line.
     */
    private const HOOKS = [
        'actionObjectProductAddAfter',
        'actionObjectProductUpdateAfter',
        'actionObjectCombinationAddAfter',
        'actionObjectCombinationUpdateAfter',
        'actionObjectSpecificPriceAddAfter',
        'actionObjectSpecificPriceUpdateAfter',
        'actionObjectSpecificPriceDeleteAfter',
        'displayProductPriceBlock',
        // Adds our API resource ciocia_promo_ends (the promotion end dates written by the importer)
        'addWebserviceResources',
    ];

    public function __construct()
    {
        $this->name = 'ciociaomnibus';
        $this->tab = 'pricing_promotion';
        $this->version = '1.0.0';
        $this->author = 'U Cioci Masali';
        $this->need_instance = 0;
        $this->ps_versions_compliancy = ['min' => '8.2.0', 'max' => _PS_VERSION_];
        $this->bootstrap = true;

        parent::__construct();

        $this->displayName = 'Cena Omnibus';
        $this->description = 'Najniższa cena z 30 dni przed obniżką dla produktów w promocji.';
    }

    public function install()
    {
        if (!parent::install() || !$this->createTables() || !$this->registerHook(self::HOOKS)) {
            return false;
        }

        // Starting rows for the products already in the shop (demo products, or an earlier import)
        CiociaPriceHistory::seed();

        return true;
    }

    /**
     * Adds what a newer version of the module needs to a shop where it is already installed: install() runs only
     * once. Both steps do nothing when already done. Called by configure-shop.php on every run.
     */
    public function updateSchema(): bool
    {
        if (!$this->createTables()) {
            return false;
        }
        // Seen on 8.2.8 right after install() in the same request: registerHook() on a hook the module already has
        // failed with a duplicate key, so only the missing ones (configure-shop.php calls this only for a shop
        // where the module was installed before)
        foreach (self::HOOKS as $hook) {
            if (!$this->isRegisteredInHook($hook) && !$this->registerHook($hook)) {
                return false;
            }
        }

        return true;
    }

    /**
     * The resource ciocia_promo_ends of the Webservice API. Its permissions are in shop/scripts/setup/webservice.php,
     * like those of PrestaShop's own resources.
     */
    public function hookAddWebserviceResources(): array
    {
        return [
            'ciocia_promo_ends' => [
                'description' => 'Promotion end dates shown on product cards (ciociaomnibus)',
                'class' => 'CiociaPromoEnd',
            ],
        ];
    }

    /** Also deletes the price history. A "Reset" in the back office does the same, as it uninstalls first. */
    public function uninstall()
    {
        return parent::uninstall()
            && $this->dropTables();
    }

    public function hookActionObjectProductAddAfter(array $params): void
    {
        CiociaPriceHistory::recordProduct((int) $params['object']->id);
    }

    public function hookActionObjectProductUpdateAfter(array $params): void
    {
        CiociaPriceHistory::recordProduct((int) $params['object']->id);
    }

    /** A combination has its own price impact, added to the product price. */
    public function hookActionObjectCombinationAddAfter(array $params): void
    {
        CiociaPriceHistory::recordProduct((int) $params['object']->id_product);
    }

    public function hookActionObjectCombinationUpdateAfter(array $params): void
    {
        CiociaPriceHistory::recordProduct((int) $params['object']->id_product);
    }

    /** A promotion is a specific price. */
    public function hookActionObjectSpecificPriceAddAfter(array $params): void
    {
        $specificPrice = $params['object'];
        if ($this->isProductPromotion($specificPrice)) {
            CiociaPriceHistory::savePromoStart((int) $specificPrice->id);
            CiociaPriceHistory::recordProduct((int) $specificPrice->id_product);
        }
    }

    public function hookActionObjectSpecificPriceUpdateAfter(array $params): void
    {
        $specificPrice = $params['object'];
        if ($this->isProductPromotion($specificPrice)) {
            CiociaPriceHistory::recordProduct((int) $specificPrice->id_product);
        }
    }

    public function hookActionObjectSpecificPriceDeleteAfter(array $params): void
    {
        $specificPrice = $params['object'];
        CiociaPriceHistory::deletePromoStart((int) $specificPrice->id);
        if ($this->isProductPromotion($specificPrice)) {
            CiociaPriceHistory::recordProduct((int) $specificPrice->id_product);
        }
    }

    /**
     * Shows the Omnibus line where the child theme asks for it with its own type:
     *   {hook h='displayProductPriceBlock' product=$product type='omnibus_price'}
     * in catalog/_partials/product-prices.tpl (product page) and catalog/_partials/miniatures/product.tpl
     * (lists). Classic's own types (old_price, unit_price, ...) are left alone; unit_price also runs in the cart.
     * Only for a product in a promotion. On the product page this file is rendered again when a combination is
     * chosen, so the line follows the selected combination.
     */
    public function hookDisplayProductPriceBlock(array $params): string
    {
        $product = $params['product'] ?? null;
        if (($params['type'] ?? '') === 'ciocia_unit_price') {
            return $this->unitPriceLine($product);
        }
        if (($params['type'] ?? '') !== 'omnibus_price' || empty($product['show_price'])
            || empty($product['has_discount'])) {
            return '';
        }

        $idProduct = (int) $product['id_product'];
        $idProductAttribute = (int) $product['id_product_attribute'];
        $currency = $this->context->currency;
        // History rows are in the default currency (CiociaPriceHistory::grossPrice), while the presented product
        // is in the visitor's currency: compare in the default one, convert once for display
        $regularPrice = Tools::convertPrice((float) $product['regular_price_amount'], $currency, false);
        $start = CiociaPriceHistory::promoStart($product['specific_prices']);
        $lowest = $start === null
            ? $regularPrice
            : CiociaOmnibusRule::lowestPrice(
                CiociaPriceHistory::rowsBefore($idProduct, $idProductAttribute, $start),
                $start,
                $regularPrice
            );

        // "-7%" and the end of the promotion, as on the source ("Cena bezpośrednio przed obniżką: 165,00 zł -7%",
        // "Promocja ważna do: 21.11.2026"); the end date is shown only when the promotion has one
        // Worked out from the two prices: for a promotion of a fixed amount PrestaShop's own discount_percentage holds
        // the amount (11.61 zł gave "-1161%")
        $percent = '';
        if ((float) $product['regular_price_amount'] > 0) {
            $percent = '-' . round((1 - (float) $product['price_amount'] / (float) $product['regular_price_amount']) * 100) . '%';
        }
        $until = '';
        $to = (string) ($product['specific_prices']['to'] ?? '');
        if ($to === '' || strpos($to, '0000-00-00') === 0) {
            // The importer leaves "to" empty so the promotion does not expire, and keeps the source's date apart
            $to = (string) CiociaPromoEnd::dateFor($idProduct, $idProductAttribute);
        }
        if ($to !== '' && strpos($to, '0000-00-00') !== 0 && ($time = strtotime($to)) !== false) {
            $until = date('d.m.Y', $time);
        }

        $locale = $this->context->getCurrentLocale();
        $this->context->smarty->assign([
            'omnibus_percent' => $percent,
            'omnibus_until' => $until,
            'omnibus_price' => $locale->formatPrice(Tools::convertPrice($lowest, $currency), $currency->iso_code),
            // Lists ask for the short two-line form with ciocia_short (the source's cards: "Cena przed" and
            // "Najniższa 30 dni"); the product page keeps the full wording
            'omnibus_short' => !empty($params['ciocia_short']),
            'omnibus_regular' => $locale->formatPrice(Tools::convertPrice($regularPrice, $currency), $currency->iso_code),
        ]);

        return $this->fetch('module:ciociaomnibus/views/templates/hook/omnibus-price.tpl');
    }

    /**
     * The unit price under the price, as on the source: "100g = 12.37 zł" (the price of 100 g or 100 ml, from the size at
     * the end of the product name: "... Najel 180g" is 22.27 / 180 * 100), and "1szt = 35.90 zł" for a product that is
     * sold as one piece: a set ("2 x 50g", "5 szt. po 125g"), or a name with no size at all.
     */
    private function unitPriceLine($product): string
    {
        $name = (string) ($product['name'] ?? '');
        $price = (float) ($product['price_amount'] ?? 0);
        if (empty($product['show_price']) || $name === '' || $price <= 0) {
            return '';
        }

        $text = $this->pricePerPiece($price);
        $isSet = preg_match('/\d\s*[x×*]\s*\d|\bszt\b|\bopak\b|\bsaszet/iu', $name);
        if (!$isSet && preg_match_all('/(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)(?![\p{L}\d])/iu', $name, $matches, PREG_SET_ORDER)) {
            $last = end($matches);
            $amount = (float) str_replace(',', '.', $last[1]);
            $unit = mb_strtolower($last[2]);
            if ($unit === 'kg' || $unit === 'l') {
                $amount *= 1000;
                $unit = $unit === 'kg' ? 'g' : 'ml';
            }
            if ($amount > 0) {
                $text = '100' . $unit . ' = ' . number_format($price / $amount * 100, 2, '.', '') . ' ' . $this->context->currency->sign;
            }
        }

        return '<p class="product-unit-price ciocia-unit-price">' . htmlspecialchars($text, ENT_QUOTES, 'UTF-8') . '</p>';
    }

    private function pricePerPiece(float $price): string
    {
        return '1szt = ' . number_format($price, 2, '.', '') . ' ' . $this->context->currency->sign;
    }

    /**
     * Skips specific prices that are not a promotion of one product: id_product 0 applies to every product,
     * and a price with id_cart belongs to a single cart (set when an employee edits an order).
     */
    private function isProductPromotion(SpecificPrice $specificPrice): bool
    {
        return (int) $specificPrice->id_product > 0 && (int) $specificPrice->id_cart === 0;
    }

    /**
     * DATETIME(6) keeps microseconds. The rule compares dates with "earlier than the promotion start", and a row
     * written in the same second as the promotion must still be told apart from it.
     * Dates come from PHP, not from the database: PrestaShop sets the time zone for PHP only (PS_TIMEZONE),
     * MariaDB uses UTC, and the "from" date of a promotion is saved in the shop's time zone.
     * id_specific_price is 0 for a row written on a save, or the ID of a promotion for a row written ahead for the
     * moment that promotion ends (CiociaPriceHistory::planPromoEnds).
     */
    private function createTables(): bool
    {
        $engine = _MYSQL_ENGINE_;
        $queries = [
            'CREATE TABLE IF NOT EXISTS `' . _DB_PREFIX_ . 'ciocia_price_history` (
                `id_price_history` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                `id_product` INT UNSIGNED NOT NULL,
                `id_product_attribute` INT UNSIGNED NOT NULL DEFAULT 0,
                `price_gross` DECIMAL(20,6) NOT NULL,
                `date_add` DATETIME(6) NOT NULL,
                `id_specific_price` INT UNSIGNED NOT NULL DEFAULT 0,
                PRIMARY KEY (`id_price_history`),
                KEY `product_date` (`id_product`, `id_product_attribute`, `date_add`)
            ) ENGINE=' . $engine . ' DEFAULT CHARSET=utf8mb4',
            'CREATE TABLE IF NOT EXISTS `' . _DB_PREFIX_ . 'ciocia_promo_start` (
                `id_specific_price` INT UNSIGNED NOT NULL,
                `date_start` DATETIME(6) NOT NULL,
                PRIMARY KEY (`id_specific_price`)
            ) ENGINE=' . $engine . ' DEFAULT CHARSET=utf8mb4',
            'CREATE TABLE IF NOT EXISTS `' . _DB_PREFIX_ . 'ciocia_promo_end` (
                `id_promo_end` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                `id_product` INT UNSIGNED NOT NULL,
                `id_product_attribute` INT UNSIGNED NOT NULL DEFAULT 0,
                `date_end` DATETIME NOT NULL,
                PRIMARY KEY (`id_promo_end`),
                UNIQUE KEY `product` (`id_product`, `id_product_attribute`)
            ) ENGINE=' . $engine . ' DEFAULT CHARSET=utf8mb4',
        ];

        foreach ($queries as $query) {
            if (!Db::getInstance()->execute($query)) {
                return false;
            }
        }

        return true;
    }

    private function dropTables(): bool
    {
        return Db::getInstance()->execute(
            'DROP TABLE IF EXISTS `' . _DB_PREFIX_ . 'ciocia_price_history`, `' . _DB_PREFIX_ . 'ciocia_promo_start`, `'
            . _DB_PREFIX_ . 'ciocia_promo_end`'
        );
    }
}
