<?php
/**
 * Omnibus price (issue #72): shows "Najniższa cena z 30 dni przed obniżką" for products in a promotion.
 *
 * PrestaShop 8.2.8 does not show this price by itself, so the module keeps its own price history:
 * - ciocia_price_history: the gross price a customer paid for a product (and combination) from a given moment,
 *   one row each time that price changes;
 * - ciocia_promo_start: when a promotion started, for promotions saved without a "from" date.
 *
 * Copied into the shop by shop/scripts/sync-code.sh and installed by shop/scripts/setup/configure-shop.php.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}
require_once __DIR__ . '/classes/CiociaOmnibusRule.php';
require_once __DIR__ . '/classes/CiociaPriceHistory.php';
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
        if (($params['type'] ?? '') !== 'omnibus_price' || empty($product['show_price'])
            || empty($product['has_discount'])) {
            return '';
        }

        $idProduct = (int) $product['id_product'];
        $idProductAttribute = (int) $product['id_product_attribute'];
        $regularPrice = (float) $product['regular_price_amount'];
        $start = CiociaPriceHistory::promoStart($product['specific_prices']);
        $lowest = $start === null
            ? $regularPrice
            : CiociaOmnibusRule::lowestPrice(
                CiociaPriceHistory::rowsBefore($idProduct, $idProductAttribute, $start),
                $start,
                $regularPrice
            );

        $this->context->smarty->assign(
            'omnibus_price',
            $this->context->getCurrentLocale()->formatPrice($lowest, $this->context->currency->iso_code)
        );

        return $this->fetch('module:ciociaomnibus/views/templates/hook/omnibus-price.tpl');
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
                PRIMARY KEY (`id_price_history`),
                KEY `product_date` (`id_product`, `id_product_attribute`, `date_add`)
            ) ENGINE=' . $engine . ' DEFAULT CHARSET=utf8mb4',
            'CREATE TABLE IF NOT EXISTS `' . _DB_PREFIX_ . 'ciocia_promo_start` (
                `id_specific_price` INT UNSIGNED NOT NULL,
                `date_start` DATETIME(6) NOT NULL,
                PRIMARY KEY (`id_specific_price`)
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
            'DROP TABLE IF EXISTS `' . _DB_PREFIX_ . 'ciocia_price_history`, `' . _DB_PREFIX_ . 'ciocia_promo_start`'
        );
    }
}
