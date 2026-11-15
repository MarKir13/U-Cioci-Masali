<?php
/**
 * Keeps the top menu (module ps_mainmenu) in step with the product categories (issue #70).
 *
 * The importer creates the categories through the Webservice API, which cannot change the menu settings,
 * and their IDs differ between installs. This module listens to PrestaShop's category events, which fire
 * for API requests too, and after every change points the menu at the top-level categories named in
 * shop/config/shop-settings.php ('catalog' => 'menu_categories'). configure-shop.php stores that list as
 * CIOCIA_MENU_CATEGORIES, installs this module and calls rebuildMenu() once.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class Ciociamenu extends Module
{
    const MENU_CATEGORIES = 'CIOCIA_MENU_CATEGORIES';
    const MENU_ITEMS = 'MOD_BLOCKTOPMENU_ITEMS';

    public function __construct()
    {
        $this->name = 'ciociamenu';
        $this->tab = 'front_office_features';
        $this->version = '1.0.0';
        $this->author = 'U Cioci Masali';
        $this->need_instance = 0;
        $this->ps_versions_compliancy = ['min' => '8.0.0', 'max' => _PS_VERSION_];
        parent::__construct();

        $this->displayName = 'Ciocia: menu kategorii';
        $this->description = 'Ustawia górne menu na kategorie z listy w shop-settings.php.';
    }

    public function install()
    {
        return parent::install()
            && $this->registerHook('actionObjectCategoryAddAfter')
            && $this->registerHook('actionObjectCategoryUpdateAfter')
            && $this->registerHook('actionObjectCategoryDeleteAfter');
    }

    public function hookActionObjectCategoryAddAfter()
    {
        $this->rebuildMenu();
    }

    public function hookActionObjectCategoryUpdateAfter()
    {
        $this->rebuildMenu();
    }

    public function hookActionObjectCategoryDeleteAfter()
    {
        $this->rebuildMenu();
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
            $idCategory = $this->topLevelCategoryId((string) $name);
            if ($idCategory) {
                $items[] = 'CAT' . $idCategory;
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
    private function topLevelCategoryId($name)
    {
        $sql = new DbQuery();
        $sql->select('c.id_category');
        $sql->from('category', 'c');
        $sql->innerJoin('category_lang', 'cl', 'cl.id_category = c.id_category AND cl.id_lang = '
            . (int) Configuration::get('PS_LANG_DEFAULT') . ' AND cl.id_shop = ' . (int) Configuration::get('PS_SHOP_DEFAULT'));
        $sql->where('c.id_parent = ' . (int) Configuration::get('PS_HOME_CATEGORY'));
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
