<?php
/**
 * Static sections of the home page (issue: home page as on the source): the category tiles, "what do you need",
 * brands, shopping guides, the SEO text and "our story". The theme calls them from templates/index.tpl:
 *
 *   {widget name='ciociahome' section='categories'}
 *
 * The text is fixed (it is the source shop's own copy). Only the links are looked up, because the ids of
 * categories and brands differ between shops: a tile points to the active category or brand with the given
 * name, the shallowest one first, and falls back to the search page when there is none.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

use PrestaShop\PrestaShop\Adapter\Image\ImageRetriever;
use PrestaShop\PrestaShop\Adapter\Presenter\Product\ProductListingPresenter;
use PrestaShop\PrestaShop\Adapter\Product\PriceFormatter;
use PrestaShop\PrestaShop\Adapter\Product\ProductColorsRetriever;
use PrestaShop\PrestaShop\Core\Module\WidgetInterface;

class CiociaHome extends Module implements WidgetInterface
{
    // Banner button -> name of the category it leads to.
    const BANNER_BUTTONS = [
        'primary' => 'Kosmetyki',
        'secondary' => 'Suplementy',
    ];

    const SECTIONS = ['featured', 'new', 'categories', 'needs', 'brands', 'guides', 'seo', 'about'];

    // Material Icons code points, as on the source. The font Classic ships has no "calculate" glyph (EA5F), so
    // that tile draws the icon as an SVG path instead of showing an empty box.
    const ICON_CALCULATE = 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5.97 4.06L14.09 6l1.41 1.41L16.91 6l1.06 1.06-1.41 1.41 1.41 1.41-1.06 1.06-1.41-1.4-1.41 1.41-1.06-1.06 1.41-1.41-1.41-1.42zm-6.78.66h5v1.5h-5v-1.5zM11.5 16h-2v2H8v-2H6v-1.5h2v-2h1.5v2h2V16zm6.5 1.25h-5v-1.5h5v1.5zm0-2.5h-5v-1.5h5v1.5z';

    const CATEGORIES = [
        ['label' => 'Kosmetyki', 'meta' => 'Naturalna pielęgnacja', 'icon' => 'E91B', 'category' => 'Kosmetyki'],
        ['label' => 'Włosy', 'meta' => 'Olejki, maski i henny', 'icon' => 'E3A0', 'category' => 'Do włosów'],
        ['label' => 'Zdrowie', 'meta' => 'Ajurwedyjskie wsparcie', 'icon' => 'E87D', 'category' => 'Zdrowie'],
        ['label' => 'Żywność', 'meta' => 'Herbaty, przyprawy i ghee', 'icon' => 'E56C', 'category' => 'Żywność'],
        ['label' => 'Joga i medytacja', 'meta' => 'Akcesoria do praktyki', 'icon' => 'EA5F', 'svg' => self::ICON_CALCULATE, 'category' => 'Akcesoria do Jogi i Medytacji'],
        ['label' => 'Nowości', 'meta' => 'Ostatnio dodane produkty', 'icon' => 'E031', 'category' => 'Nowości'],
        ['label' => 'Prezenty', 'meta' => 'Wyjątkowe inspiracje', 'icon' => 'E8F6', 'category' => 'NA PREZENT'],
    ];

    const NEEDS = [
        ['label' => 'Odporność', 'icon' => '🛡', 'category' => 'Odporność'],
        ['label' => 'Stres i równowaga', 'icon' => '🌿', 'category' => 'Stres'],
        ['label' => 'Dobre trawienie', 'icon' => '🫖', 'category' => 'Dobre Trawienie'],
        ['label' => 'Witalność i energia', 'icon' => '✨', 'category' => 'Witalność i Energia'],
        ['label' => 'Pielęgnacja włosów', 'icon' => '🪷', 'category' => 'Do włosów'],
        ['label' => 'Pielęgnacja twarzy', 'icon' => '🌸', 'category' => 'Do twarzy'],
    ];

    const BRANDS = [
        ['label' => 'Dabur', 'meta' => 'Olejki, maski i pielęgnacja'],
        ['label' => 'Organic India', 'meta' => 'Zioła, suplementy i herbaty'],
        ['label' => 'Himalaya', 'meta' => 'Kosmetyki i suplementy'],
        ['label' => 'Yogi Tea', 'meta' => 'Ajurwedyjskie mieszanki herbat'],
        ['label' => 'Sesa', 'meta' => 'Ajurwedyjskie olejki do włosów'],
    ];

    // The source links to its own articles; here the guides lead to the matching categories
    const GUIDES = [
        [
            'icon' => 'E3A0',
            'title' => 'Jak dobrać pielęgnację włosów?',
            'text' => 'Porównaj ajurwedyjskie olejki, maski Vatika, szampony oraz naturalne henny.',
            'link' => 'Przejdź do pielęgnacji włosów',
            'category' => 'Do włosów',
            'cms' => 'jak-dobrac-pielegnacje-wlosow',
        ],
        [
            'icon' => 'E87D',
            'title' => 'Poznaj suplementy ajurwedyjskie',
            'text' => 'Odkryj produkty Himalaya i Organic India wraz z przejrzystym składem i sposobem użycia.',
            'link' => 'Zobacz suplementy',
            'category' => 'Suplementy',
            'cms' => 'suplementy-ajurwedyjskie-przewodnik',
        ],
        [
            'icon' => 'E050',
            'title' => 'Misy tybetańskie i medytacja',
            'text' => 'Wybierz misy, gongi, dzwonki i akcesoria pomagające stworzyć przestrzeń do praktyki.',
            'link' => 'Odkryj misy i gongi',
            'category' => 'Misy tybetańskie, gongi, dzwonki i cymbałki',
            'cms' => 'misy-tybetanskie-przewodnik',
        ],
    ];

    // Words of the SEO paragraph that link to a category or a brand
    const SEO_LINKS = [
        'kosmetyki' => ['category', 'Kosmetyki'],
        'suplementy' => ['category', 'Suplementy'],
        'organic' => ['brand', 'Organic India'],
        'yogi' => ['brand', 'Yogi Tea'],
        'himalaya' => ['brand', 'Himalaya'],
        'sesa' => ['brand', 'Sesa'],
        'dabur' => ['brand', 'Dabur'],
    ];

    public function __construct()
    {
        $this->name = 'ciociahome';
        $this->tab = 'front_office_features';
        $this->version = '1.0.0';
        $this->author = 'U Cioci Masali';
        $this->need_instance = 0;
        $this->ps_versions_compliancy = ['min' => '8.0.0', 'max' => _PS_VERSION_];

        parent::__construct();

        $this->displayName = 'Ciocia home page sections';
        $this->description = 'Category tiles, needs, brands, guides, SEO text and story on the home page.';
    }

    public function renderWidget($hookName = null, array $configuration = [])
    {
        $section = isset($configuration['section']) ? (string) $configuration['section'] : '';
        if ($section === 'banner-url') {
            return $this->bannerUrl(isset($configuration['button']) ? (string) $configuration['button'] : '');
        }
        if (!in_array($section, self::SECTIONS, true)) {
            return '';
        }
        $this->smarty->assign($this->getWidgetVariables($hookName, $configuration));

        return $this->fetch('module:ciociahome/views/templates/widget/' . $section . '.tpl');
    }

    public function getWidgetVariables($hookName = null, array $configuration = [])
    {
        $section = isset($configuration['section']) ? (string) $configuration['section'] : '';
        $vars = [];
        switch ($section) {
            case 'featured':
                $vars['products'] = $this->featuredProducts(8);
                $vars['ciocia_all_url'] = $this->categoryUrl('Nowości');
                break;
            case 'new':
                $vars['products'] = $this->newProducts(8);
                $vars['ciocia_all_url'] = $this->categoryUrl('Nowości');
                break;
            case 'categories':
                $vars['ciocia_categories'] = $this->withCategoryUrls(self::CATEGORIES);
                break;
            case 'needs':
                $vars['ciocia_needs'] = $this->withCategoryUrls(self::NEEDS);
                break;
            case 'brands':
                $vars['ciocia_brands'] = $this->withBrandUrls(self::BRANDS);
                break;
            case 'guides':
                $vars['ciocia_guides'] = $this->withGuideUrls(self::GUIDES);
                break;
            case 'seo':
                $vars['ciocia_seo_urls'] = $this->seoUrls();
                break;
            case 'about':
                $vars['ciocia_free_shipping'] = (int) Configuration::get('PS_SHIPPING_FREE_PRICE');
                $vars['ciocia_gallery'] = $this->gallery();
                $vars['ciocia_email'] = (string) Configuration::get('PS_SHOP_EMAIL');
                break;
        }

        return $vars;
    }

    /**
     * "Polecane produkty": Classic's module (ps_featuredproducts) takes the products of the Home category, and the
     * importer puts none there, so the section would be empty. Instead: up to $limit active, visible products in
     * stock with a photo, one from each category (the order is fixed, but mixed, not by category id), presented
     * like the products of a category listing.
     */
    private function featuredProducts($limit)
    {
        $idShop = (int) $this->context->shop->id;
        $ids = Db::getInstance()->executeS(
            'SELECT MIN(p.id_product) AS id_product FROM ' . _DB_PREFIX_ . 'product p'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_shop ps ON ps.id_product = p.id_product'
            . ' AND ps.id_shop = ' . $idShop . ' AND ps.active = 1 AND ps.visibility IN (\'both\', \'catalog\')'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'image_shop ims ON ims.id_product = p.id_product'
            . ' AND ims.id_shop = ' . $idShop . ' AND ims.cover = 1'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'stock_available sa ON sa.id_product = p.id_product'
            . ' AND sa.id_product_attribute = 0 AND sa.quantity > 0'
            . ' GROUP BY ps.id_category_default ORDER BY CRC32(MIN(p.id_product)) LIMIT ' . (int) $limit
        );
        if (!$ids) {
            return [];
        }

        return $this->presentProducts($ids);
    }

    /**
     * "Nowości": Classic's module (ps_newproducts) has the title "Nowe produkty"; the source calls the section
     * "Nowości" with the eyebrow "Właśnie dotarły". The newest 8 active, visible products in stock with a photo.
     */
    private function newProducts($limit)
    {
        $idShop = (int) $this->context->shop->id;
        $ids = Db::getInstance()->executeS(
            'SELECT p.id_product FROM ' . _DB_PREFIX_ . 'product p'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_shop ps ON ps.id_product = p.id_product'
            . ' AND ps.id_shop = ' . $idShop . ' AND ps.active = 1 AND ps.visibility IN (\'both\', \'catalog\')'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'image_shop ims ON ims.id_product = p.id_product'
            . ' AND ims.id_shop = ' . $idShop . ' AND ims.cover = 1'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'stock_available sa ON sa.id_product = p.id_product'
            . ' AND sa.id_product_attribute = 0 AND sa.quantity > 0'
            . ' ORDER BY ps.date_add DESC, p.id_product DESC LIMIT ' . (int) $limit
        );

        return $ids ? $this->presentProducts($ids) : [];
    }

    private function presentProducts(array $ids)
    {
        $assembler = new ProductAssembler($this->context);
        $factory = new ProductPresenterFactory($this->context);
        $settings = $factory->getPresentationSettings();
        $presenter = new ProductListingPresenter(
            new ImageRetriever($this->context->link),
            $this->context->link,
            new PriceFormatter(),
            new ProductColorsRetriever(),
            $this->context->getTranslator()
        );
        $products = [];
        foreach ($ids as $row) {
            $products[] = $presenter->present(
                $settings,
                $assembler->assembleProduct(['id_product' => (int) $row['id_product']]),
                $this->context->language
            );
        }

        return $products;
    }

    /**
     * A guide leads to its article, a CMS page (created by shop-content.php), as on the source. Without the page
     * it falls back to the category the guide is about.
     */
    private function withGuideUrls(array $items)
    {
        foreach ($items as &$item) {
            $id = (int) Db::getInstance()->getValue(
                'SELECT id_cms FROM ' . _DB_PREFIX_ . 'cms_lang WHERE link_rewrite = \'' . pSQL($item['cms']) . '\''
                . ' AND id_lang = ' . (int) $this->context->language->id
            );
            $item['url'] = $id ? $this->context->link->getCMSLink($id) : $this->categoryUrl($item['category']);
        }

        return $items;
    }

    private function withCategoryUrls(array $items)
    {
        foreach ($items as &$item) {
            $item['url'] = $this->categoryUrl($item['category']);
        }

        return $items;
    }

    private function withBrandUrls(array $items)
    {
        foreach ($items as &$item) {
            $item['url'] = $this->brandUrl($item['label']);
        }

        return $items;
    }

    private function seoUrls()
    {
        $urls = [];
        foreach (self::SEO_LINKS as $key => $target) {
            $urls[$key] = $target[0] === 'brand' ? $this->brandUrl($target[1]) : $this->categoryUrl($target[1]);
        }

        return $urls;
    }

    /**
     * Link to the active category with this name in the current language, the one nearest the root first.
     */
    /**
     * Link of a home banner button: the category named in BANNER_BUTTONS. The setup scripts run before the
     * import, when those categories do not exist yet, so slider.tpl asks for the link here on every page view.
     * Returns '' when there is no such category (the template then uses the link saved at install).
     */
    private function bannerUrl($button)
    {
        $names = self::BANNER_BUTTONS;
        if (!isset($names[$button])) {
            return '';
        }
        $id = $this->categoryId($names[$button]);
        if (!$id) {
            return '';
        }
        $url = $this->context->link->getCategoryLink($id);

        return parse_url($url, PHP_URL_PATH) ?: $url;
    }

    private function categoryId($name)
    {
        return (int) Db::getInstance()->getValue(
            'SELECT c.id_category FROM ' . _DB_PREFIX_ . 'category c'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'category_lang cl ON cl.id_category = c.id_category'
            . ' AND cl.id_lang = ' . (int) $this->context->language->id
            . ' AND cl.id_shop = ' . (int) $this->context->shop->id
            . ' WHERE c.active = 1 AND cl.name = \'' . pSQL($name) . '\''
            . ' ORDER BY c.level_depth, c.id_category'
        );
    }

    private function categoryUrl($name)
    {
        $link = $this->context->link;
        $id = (int) Db::getInstance()->getValue(
            'SELECT c.id_category FROM ' . _DB_PREFIX_ . 'category c'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'category_lang cl ON cl.id_category = c.id_category'
            . ' AND cl.id_lang = ' . (int) $this->context->language->id
            . ' AND cl.id_shop = ' . (int) $this->context->shop->id
            . ' WHERE c.active = 1 AND cl.name = \'' . pSQL($name) . '\''
            . ' ORDER BY c.level_depth, c.id_category'
        );

        return $id ? $link->getCategoryLink($id) : $this->searchUrl($name);
    }

    private function brandUrl($name)
    {
        $id = (int) Manufacturer::getIdByName($name);

        return $id ? $this->context->link->getManufacturerLink($id) : $this->searchUrl($name);
    }

    private function searchUrl($query)
    {
        return $this->context->link->getPageLink('search', true, null, ['s' => $query]);
    }

    /**
     * The two photos of the old shop, if they are in the theme (assets/img/home-banner/home-store-1.jpg and -2.jpg).
     */
    private function gallery()
    {
        $photos = [];
        foreach ([1, 2] as $number) {
            $file = 'home-store-' . $number . '.jpg';
            if (is_file(_PS_ALL_THEMES_DIR_ . 'ciocia/assets/img/home-banner/' . $file)) {
                $photos[] = $this->context->link->getBaseLink() . 'themes/ciocia/assets/img/home-banner/' . $file;
            }
        }

        return $photos;
    }
}
