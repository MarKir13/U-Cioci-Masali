<?php
/**
 * Price history for the Omnibus price (issue #72): writes ciocia_price_history and ciocia_promo_start.
 *
 * A row holds the gross price a visitor sees from that moment on, with any promotion in effect then.
 * Products with combinations get one row per combination; a product without them gets id_product_attribute 0.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class CiociaPriceHistory
{
    /** Adds a row for every combination (or the product itself) whose price differs from its last row. */
    public static function recordProduct(int $idProduct): void
    {
        if ($idProduct <= 0) {
            return;
        }

        // PrestaShop keeps prices and specific prices in memory for the rest of the request. The object hooks run
        // inside ObjectModel::add/update/delete, before SpecificPrice clears that memory itself, so without this
        // a promotion just added or deleted would not change the price yet.
        SpecificPrice::flushCache();
        foreach (self::combinationIds($idProduct) as $idProductAttribute) {
            $price = self::grossPrice($idProduct, $idProductAttribute, true);
            $last = self::lastPrice($idProduct, $idProductAttribute);
            if ($last === null || abs($last - $price) >= 0.005) {
                self::insert($idProduct, $idProductAttribute, $price);
            }
        }
    }

    /**
     * Starting rows: the regular price (without promotions) for every product and combination that has no row
     * yet, and a start date for every promotion that has none. Safe to run again. Returns the number of new rows.
     */
    public static function seed(): int
    {
        $db = Db::getInstance();
        $missing = $db->executeS(
            'SELECT p.id_product, IFNULL(pa.id_product_attribute, 0) AS id_product_attribute
            FROM `' . _DB_PREFIX_ . 'product` p
            LEFT JOIN `' . _DB_PREFIX_ . 'product_attribute` pa ON pa.id_product = p.id_product
            WHERE NOT EXISTS (
                SELECT 1 FROM `' . _DB_PREFIX_ . 'ciocia_price_history` h
                WHERE h.id_product = p.id_product
                    AND h.id_product_attribute = IFNULL(pa.id_product_attribute, 0)
            )',
            true,
            false
        );

        SpecificPrice::flushCache();
        foreach ($missing as $row) {
            $idProduct = (int) $row['id_product'];
            $idProductAttribute = (int) $row['id_product_attribute'];
            self::insert($idProduct, $idProductAttribute, self::grossPrice($idProduct, $idProductAttribute, false));
        }

        // After the rows above, so a promotion that is already running starts after its regular price
        $db->execute(
            'INSERT IGNORE INTO `' . _DB_PREFIX_ . 'ciocia_promo_start` (id_specific_price, date_start)
            SELECT id_specific_price, \'' . self::now() . '\'
            FROM `' . _DB_PREFIX_ . 'specific_price`
            WHERE id_cart = 0'
        );

        return count($missing);
    }

    /** Remembers when a promotion was added. The rule uses it when the promotion has no "from" date. */
    public static function savePromoStart(int $idSpecificPrice): void
    {
        Db::getInstance()->insert(
            'ciocia_promo_start',
            ['id_specific_price' => $idSpecificPrice, 'date_start' => self::now()],
            false,
            true,
            Db::INSERT_IGNORE
        );
    }

    /**
     * When a promotion started: its "from" date, or for a promotion without one, the date saved when it was
     * added. Null when neither is known (for example a promotion added while the module was not installed and
     * before seed() ran); the caller then shows the regular price.
     *
     * @param array|false $specificPrice the specific price PrestaShop applied, as in $product.specific_prices
     */
    public static function promoStart($specificPrice): ?DateTimeImmutable
    {
        if (!is_array($specificPrice) || empty($specificPrice['id_specific_price'])) {
            return null;
        }
        if (!empty($specificPrice['from']) && $specificPrice['from'] !== '0000-00-00 00:00:00') {
            return new DateTimeImmutable($specificPrice['from']);
        }

        $date = Db::getInstance()->getValue(
            'SELECT date_start FROM `' . _DB_PREFIX_ . 'ciocia_promo_start`
            WHERE id_specific_price = ' . (int) $specificPrice['id_specific_price'],
            false
        );

        return $date === false ? null : new DateTimeImmutable($date);
    }

    /** History rows saved before $before, oldest first, as CiociaOmnibusRule::lowestPrice expects them. */
    public static function rowsBefore(int $idProduct, int $idProductAttribute, DateTimeImmutable $before): array
    {
        return Db::getInstance()->executeS(
            'SELECT price_gross, date_add FROM `' . _DB_PREFIX_ . 'ciocia_price_history`
            WHERE id_product = ' . $idProduct . ' AND id_product_attribute = ' . $idProductAttribute . '
                AND date_add < \'' . $before->format('Y-m-d H:i:s.u') . '\'
            ORDER BY date_add, id_price_history',
            true,
            false
        );
    }

    public static function deletePromoStart(int $idSpecificPrice): void
    {
        Db::getInstance()->delete('ciocia_promo_start', 'id_specific_price = ' . $idSpecificPrice);
    }

    /**
     * The current date with microseconds, in the shop's time zone (PS_TIMEZONE, set by PrestaShop for PHP).
     * Not NOW() in SQL: MariaDB uses UTC, while promotion "from" dates are in the shop's time zone.
     */
    public static function now(): string
    {
        return (new DateTimeImmutable())->format('Y-m-d H:i:s.u');
    }

    /** IDs of the product's combinations, or [0] for a product without combinations. */
    private static function combinationIds(int $idProduct): array
    {
        $rows = Db::getInstance()->executeS(
            'SELECT id_product_attribute FROM `' . _DB_PREFIX_ . 'product_attribute` WHERE id_product = ' . $idProduct,
            true,
            false
        );
        $ids = array_map('intval', array_column($rows, 'id_product_attribute'));

        return $ids === [] ? [0] : $ids;
    }

    /**
     * The gross price a visitor sees: default shop, country and currency, the visitor group, quantity 1.
     * Set explicitly, because in the back office and the Webservice API the context has no storefront customer.
     */
    private static function grossPrice(int $idProduct, int $idProductAttribute, bool $withPromotion): float
    {
        $specificPrice = null;
        $price = Product::priceCalculation(
            (int) Configuration::get('PS_SHOP_DEFAULT'),
            $idProduct,
            $idProductAttribute,
            (int) Configuration::get('PS_COUNTRY_DEFAULT'),
            0,
            '',
            (int) Configuration::get('PS_CURRENCY_DEFAULT'),
            (int) Configuration::get('PS_UNIDENTIFIED_GROUP'),
            1,
            true,
            6,
            false,
            $withPromotion,
            true,
            $specificPrice,
            true
        );

        return round((float) $price, 2);
    }

    private static function lastPrice(int $idProduct, int $idProductAttribute): ?float
    {
        $price = Db::getInstance()->getValue(
            'SELECT price_gross FROM `' . _DB_PREFIX_ . 'ciocia_price_history`
            WHERE id_product = ' . $idProduct . ' AND id_product_attribute = ' . $idProductAttribute . '
            ORDER BY date_add DESC, id_price_history DESC',
            false
        );

        return $price === false ? null : (float) $price;
    }

    private static function insert(int $idProduct, int $idProductAttribute, float $price): void
    {
        Db::getInstance()->insert('ciocia_price_history', [
            'id_product' => $idProduct,
            'id_product_attribute' => $idProductAttribute,
            'price_gross' => $price,
            'date_add' => self::now(),
        ]);
    }
}
