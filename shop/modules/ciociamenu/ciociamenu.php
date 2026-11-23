<?php
/**
 * Keeps the storefront in step with the catalogue the importer writes through the Webservice API (issue #70).
 *
 * 1. The top menu (module ps_mainmenu). The API cannot change the menu settings, and category IDs differ
 *    between installs. After every category change this module points the menu at the top-level categories
 *    named in shop/config/shop-settings.php ('catalog' => 'menu_categories').
 * 2. The page cache. The home page sections (new products, specials, featured, best sellers) are cached by
 *    Smarty and cleared by hooks that only the back office fires, so after an API write they would keep old
 *    prices, stock and images. After every change to a product, a combination, a specific price, a stock row,
 *    an image or a category, this module clears that cache.
 *
 * Both work through PrestaShop's object events (actionObject...After), which fire for API requests too.
 * configure-shop.php stores the menu list as CIOCIA_MENU_CATEGORIES, installs this module, registers its
 * hooks and calls rebuildMenu() once.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class Ciociamenu extends Module
{
    const MENU_CATEGORIES = 'CIOCIA_MENU_CATEGORIES';
    const MENU_ITEMS = 'MOD_BLOCKTOPMENU_ITEMS';

    // Fired for every object PrestaShop saves or deletes; the module reacts only to CATALOG_CLASSES
    const HOOKS = ['actionObjectAddAfter', 'actionObjectUpdateAfter', 'actionObjectDeleteAfter'];
    // CiociaPromoEnd: the promotion end dates shown on product cards (module ciociaomnibus, #111)
    const CATALOG_CLASSES = [
        'Category', 'Manufacturer', 'Product', 'Combination', 'SpecificPrice', 'StockAvailable', 'Image', 'CiociaPromoEnd',
    ];

    public function __construct()
    {
        $this->name = 'ciociamenu';
        $this->tab = 'front_office_features';
        $this->version = '1.0.0';
        $this->author = 'U Cioci Masali';
        $this->need_instance = 0;
        $this->ps_versions_compliancy = ['min' => '8.0.0', 'max' => _PS_VERSION_];
        parent::__construct();

        $this->displayName = 'Ciocia: menu kategorii i odświeżanie katalogu';
        $this->description = 'Ustawia górne menu na kategorie z listy w shop-settings.php i czyści pamięć '
            . 'podręczną stron po zmianach katalogu, także przez API.';
    }

    public function install()
    {
        return parent::install() && $this->registerHooks();
    }

    /** Safe to call again: PrestaShop skips a hook the module is already registered on. */
    public function registerHooks()
    {
        return $this->registerHook(self::HOOKS);
    }

    public function hookActionObjectAddAfter($params)
    {
        $this->catalogChanged($params['object']);
    }

    public function hookActionObjectUpdateAfter($params)
    {
        $this->catalogChanged($params['object']);
    }

    public function hookActionObjectDeleteAfter($params)
    {
        $this->catalogChanged($params['object']);
    }

    private function catalogChanged($object)
    {
        // get_class() gives the class without "Core" (SpecificPrice, not SpecificPriceCore)
        if (!in_array(get_class($object), self::CATALOG_CLASSES, true)) {
            return;
        }
        // A brand link can only be built once the brand exists, and the importer creates brands after categories
        if ($object instanceof Category || $object instanceof Manufacturer) {
            $this->rebuildMenu();
        }
        // The cached page parts only, not the compiled templates (Tools::clearSmartyCache() would drop those
        // too and make the next page views slow). Cheap while the cache is empty, as during an import.
        Tools::clearCache();
    }

    /**
     * Points the menu at the listed top-level categories that exist, in the listed order, and returns the
     * menu items (such as "CAT12,CAT40"). Without a list it leaves the menu alone.
     */
    public function rebuildMenu()
    {
        $names = json_decode((string) Configuration::get(self::MENU_CATEGORIES), true);
        if (!is_array($names)) {
            return (string) Configuration::get(self::MENU_ITEMS);
        }

        $items = [];
        foreach ($names as $name) {
            if (is_array($name)) {
                // A link under its own label to a brand page ("manufacturer", e.g. "Himalaya") or, when the
                // brand does not exist (yet), to a category at any level ("category")
                $path = '';
                if (!empty($name['manufacturer'])) {
                    $idManufacturer = (int) Manufacturer::getIdByName((string) $name['manufacturer']);
                    if ($idManufacturer) {
                        $path = (string) parse_url(Context::getContext()->link->getManufacturerLink($idManufacturer), PHP_URL_PATH);
                    }
                }
                if ($path === '' && !empty($name['category'])) {
                    $idCategory = $this->topLevelCategoryId((string) $name['category'], true);
                    if ($idCategory) {
                        $path = (string) parse_url(Context::getContext()->link->getCategoryLink($idCategory), PHP_URL_PATH);
                    }
                }
                if ($path !== '') {
                    $idLink = $this->ensureLink((string) $name['label'], $path);
                    if ($idLink) {
                        $items[] = 'LNK' . $idLink;
                    }
                }
                continue;
            }
            $idCategory = $this->topLevelCategoryId((string) $name);
            if ($idCategory) {
                $items[] = 'CAT' . $idCategory;
            } elseif (mb_strtolower((string) $name) === 'promocje') {
                // Not a category: the source shop's "Promocje" entry points to the price-drop page
                $idLink = $this->ensureLink('Promocje', $this->pricesDropPath());
                if ($idLink) {
                    $items[] = 'LNK' . $idLink;
                }
            }
        }
        $value = implode(',', $items);

        // ps_mainmenu reads the value for the current shop and falls back to the global one, so both are set
        Configuration::updateGlobalValue(self::MENU_ITEMS, $value);
        foreach (Shop::getShops(false, null, true) as $idShop) {
            Configuration::updateValue(self::MENU_ITEMS, $value, false, Shop::getGroupFromShop($idShop), $idShop);
        }
        $this->clearMainMenuCache(_PS_CACHE_DIR_ . 'ps_mainmenu');

        return $value;
    }

    /** ID of the category with this name directly under Home, or 0. */
    // Path of PrestaShop's own price-drop page (/promocje), relative so it works on any host and port
    private function pricesDropPath()
    {
        $path = parse_url(Context::getContext()->link->getPageLink('prices-drop'), PHP_URL_PATH);

        return $path ?: '/promocje';
    }

    // The custom link of ps_mainmenu (tables linksmenutop and linksmenutop_lang): created once, updated afterwards
    private function ensureLink($label, $path)
    {
        $idShop = (int) Configuration::get('PS_SHOP_DEFAULT');
        $db = Db::getInstance();
        $id = (int) $db->getValue('SELECT l.id_linksmenutop FROM ' . _DB_PREFIX_ . 'linksmenutop_lang l WHERE l.label = "'
            . pSQL($label) . '" AND l.id_shop = ' . $idShop);
        if (!$id) {
            if (!$db->insert('linksmenutop', ['new_window' => 0, 'id_shop' => $idShop])) {
                return 0;
            }
            $id = (int) $db->Insert_ID();
        }
        // Not REPLACE INTO: the table of ps_mainmenu has no unique key, so REPLACE never replaced anything and added
        // a row on every call (rebuildMenu runs after each category and brand the importer saves), and the menu
        // kept reading the oldest row. Delete the rows of the link first, which also removes copies made earlier.
        foreach (Language::getLanguages(false) as $language) {
            $idLang = (int) $language['id_lang'];
            $db->execute('DELETE FROM ' . _DB_PREFIX_ . 'linksmenutop_lang WHERE id_linksmenutop = ' . $id
                . ' AND id_lang = ' . $idLang . ' AND id_shop = ' . $idShop);
            $db->execute('INSERT INTO ' . _DB_PREFIX_ . 'linksmenutop_lang (id_linksmenutop, id_lang, id_shop, label, link) VALUES ('
                . $id . ', ' . $idLang . ', ' . $idShop . ', "' . pSQL($label) . '", "' . pSQL($path) . '")');
        }

        return $id;
    }

    private function topLevelCategoryId($name, $anyLevel = false)
    {
        $sql = new DbQuery();
        $sql->select('c.id_category');
        $sql->from('category', 'c');
        $sql->innerJoin('category_lang', 'cl', 'cl.id_category = c.id_category AND cl.id_lang = '
            . (int) Configuration::get('PS_LANG_DEFAULT') . ' AND cl.id_shop = ' . (int) Configuration::get('PS_SHOP_DEFAULT'));
        if (!$anyLevel) {
            $sql->where('c.id_parent = ' . (int) Configuration::get('PS_HOME_CATEGORY'));
        }
        $sql->where('cl.name = "' . pSQL($name) . '"');
        $sql->orderBy('c.id_category');

        return (int) Db::getInstance()->getValue($sql);
    }

    /**
     * ps_mainmenu keeps the built menu in JSON files and has no public method to clear them, so the files
     * are deleted here the same way it does it itself (only *.json, folders stay).
     */
    private function clearMainMenuCache($dir)
    {
        if (!is_dir($dir)) {
            return;
        }
        foreach (scandir($dir) as $entry) {
            if ($entry === '.' || $entry === '..') {
                continue;
            }
            $path = $dir . DIRECTORY_SEPARATOR . $entry;
            if (is_dir($path)) {
                $this->clearMainMenuCache($path);
            } elseif (substr($entry, -5) === '.json') {
                unlink($path);
            }
        }
    }
}
