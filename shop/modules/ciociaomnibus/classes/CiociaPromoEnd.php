<?php
/**
 * The end date of a promotion as the source shop shows it (issue #111): "Cena przed: 26,50 zł · do 14.11.2026".
 *
 * Kept apart from the specific price on purpose. The source's promotions end within days (most of the scraped
 * ones on 14.11.2026), and PrestaShop stops applying a specific price after its "to" date, so writing the date
 * there would end every promotion of our shop and break D3 (20+ promotions). The importer leaves "to" empty and
 * writes the date here; the module only shows it. The Omnibus rule never reads this table.
 *
 * One row per product and combination (id_product_attribute 0 for a product without combinations). The importer
 * writes it through the Webservice API as the resource "ciocia_promo_ends" (hookAddWebserviceResources).
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class CiociaPromoEnd extends ObjectModel
{
    /** @var int */
    public $id_product;

    /** @var int */
    public $id_product_attribute = 0;

    /** @var string */
    public $date_end;

    public static $definition = [
        'table' => 'ciocia_promo_end',
        'primary' => 'id_promo_end',
        'fields' => [
            'id_product' => ['type' => self::TYPE_INT, 'validate' => 'isUnsignedId', 'required' => true],
            'id_product_attribute' => ['type' => self::TYPE_INT, 'validate' => 'isUnsignedId'],
            'date_end' => ['type' => self::TYPE_DATE, 'validate' => 'isDate', 'required' => true],
        ],
    ];

    /** Names of the resource in the API's XML and JSON: <ciocia_promo_ends><ciocia_promo_end>. */
    protected $webserviceParameters = [
        'objectsNodeName' => 'ciocia_promo_ends',
        'objectNodeName' => 'ciocia_promo_end',
    ];

    /**
     * The end date of a product's (or combination's) promotion, or null when it has none.
     * Also null when the table is missing: a shop rebuilt with this code before configure-shop.php ran again
     * (ciociaomnibus::updateSchema). The error would otherwise hide the whole Omnibus line on every card.
     */
    public static function dateFor(int $idProduct, int $idProductAttribute): ?string
    {
        try {
            $date = Db::getInstance()->getValue(
                'SELECT `date_end` FROM `' . _DB_PREFIX_ . 'ciocia_promo_end`
                 WHERE `id_product` = ' . $idProduct . ' AND `id_product_attribute` = ' . $idProductAttribute
            );
        } catch (PrestaShopException $exception) {
            return null;
        }

        return $date ? (string) $date : null;
    }

    /**
     * Deletes the end dates of a deleted product (all its rows), or of one deleted combination. Called by the
     * module's object hooks, so it works for the importer and the back office alike. Plain SQL: deleting through
     * ObjectModel would run the object hooks again. Does nothing when the table is missing (see dateFor()).
     */
    public static function deleteFor(int $idProduct, ?int $idProductAttribute = null): void
    {
        $where = '`id_product` = ' . $idProduct;
        if ($idProductAttribute !== null) {
            $where .= ' AND `id_product_attribute` = ' . $idProductAttribute;
        }
        try {
            Db::getInstance()->delete('ciocia_promo_end', $where);
        } catch (PrestaShopException $exception) {
            // No table yet: nothing to delete
        }
    }
}
