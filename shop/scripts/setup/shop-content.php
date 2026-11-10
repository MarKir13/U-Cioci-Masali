<?php
// Puts the shop's own content into the database (issue #27): store details, CMS pages and footer
// links, and switches off Classic demo content that the source shop does not have.
//
// Runs once after the automatic install (post-install/20-shop-content.sh). Safe to run again: it finds
// records by link_rewrite or position, updates them in place and never creates duplicates.
// Change content here or in cms/*.html, not in the back office: back office changes are lost on
// `down -v` and never reach the rest of the team.

use PrestaShop\Module\LinkList\Model\LinkBlock;

require __DIR__ . '/bootstrap.php';
$values = require __DIR__ . '/values.php';

// CMS pages in footer order: link_rewrite => [title, meta description].
// The page text is in cms/<link_rewrite>.html. {{name}} placeholders are filled in from values.php
// (see placeholders() below).
const CMS_PAGES = [
    'o-sklepie' => ['O sklepie', 'Kim jesteśmy i jakie produkty z Indii znajdziesz w naszym sklepie.'],
    'regulamin' => ['Regulamin', 'Zasady składania zamówień, płatności, dostawy, zwrotów i reklamacji.'],
    'polityka-prywatnosci' => ['Polityka prywatności', 'Jakie dane zbieramy, w jakim celu i jakie masz prawa.'],
    'dostawa' => ['Dostawa', 'Formy i koszty dostawy, czas wysyłki i darmowa dostawa.'],
    'formy-platnosci' => ['Formy płatności', 'Przelew bankowy i płatność przy odbiorze.'],
    'zwrot-towaru' => ['Zwrot towaru - odstąpienie od umowy', 'Jak w ciągu 14 dni odstąpić od umowy i odesłać towar.'],
];

// The page linked as the terms and conditions in checkout and registration.
const TERMS_PAGE = 'regulamin';

// The installer's English demo pages, deleted by link_rewrite.
const DEMO_CMS_PAGES = ['delivery', 'legal-notice', 'terms-and-conditions-of-use', 'about-us', 'secure-payment'];

// Footer link blocks (module ps_linklist, hook displayFooter), from left to right.
// 'cms' takes link_rewrites from CMS_PAGES; 'product' and 'static' take PrestaShop page names.
// The module always shows a block's links in this order: cms, product, static.
const FOOTER_BLOCKS = [
    [
        'name' => 'Produkty',
        'cms' => [],
        'product' => ['prices-drop', 'new-products'],
        'static' => [],
    ],
    [
        'name' => 'Nasza firma',
        'cms' => ['o-sklepie', 'regulamin', 'polityka-prywatnosci', 'dostawa', 'formy-platnosci', 'zwrot-towaru'],
        'product' => [],
        'static' => ['contact', 'sitemap'],
    ],
];

// Titles of PrestaShop's own pages. They are the link text in the footer and the page <title>.
const PAGE_TITLES = [
    'contact' => 'Kontakt',
];

// Classic demo modules with no equivalent in our shop yet. Disabled, not uninstalled, so a later
// issue can enable one again with our own content (for example ps_imageslider for a home banner).
const DEMO_MODULES = [
    'ps_imageslider',   // "Sample 1-3" slides on the home page
    'ps_banner',        // demo sale banner on the home page
    'ps_customtext',    // lorem ipsum block on the home page
    'blockreassurance', // "(edit with the Customer Reassurance module)" on product, cart and checkout
];

// Texts under checkboxes in registration and checkout, by configuration key.
const FORM_TEXTS = [
    // Customer data privacy (module ps_dataprivacy). The installer leaves it in English.
    'CUSTPRIV_MSG_AUTH' => 'Twoje dane osobowe wykorzystujemy do realizacji zamówień i odpowiedzi na pytania. '
        . 'W każdej chwili możesz je poprawić lub usunąć. Szczegóły znajdziesz w polityce prywatności.',
    // Newsletter (module ps_emailsubscription). The installer's text points to the deleted legal notice page.
    'NW_CONDITIONS' => 'Możesz zrezygnować w każdej chwili. Link do wypisania się znajdziesz w każdym e-mailu z newslettera.',
];

function setStoreDetails(array $shop): void
{
    // Shown in the footer and on the contact page (module ps_contactinfo), and used as the sender
    // name and address of shop e-mails.
    Configuration::updateValue('PS_SHOP_NAME', $shop['name']);
    Configuration::updateValue('PS_SHOP_EMAIL', $shop['email']);
    Configuration::updateValue('PS_SHOP_ADDR1', $shop['address1']);
    Configuration::updateValue('PS_SHOP_ADDR2', '');
    Configuration::updateValue('PS_SHOP_CODE', $shop['postcode']);
    Configuration::updateValue('PS_SHOP_CITY', $shop['city']);
    Configuration::updateValue('PS_SHOP_COUNTRY_ID', (int) Country::getByIso($shop['country_iso']));

    // The shop record has a name of its own, shown in the back office.
    $record = new Shop((int) Configuration::get('PS_SHOP_DEFAULT'));
    if ($record->name !== $shop['name']) {
        $record->name = $shop['name'];
        mustSave($record->update(), 'shop name');
    }
    say('Store details: ' . $shop['name'] . ', ' . $shop['address1'] . ', ' . $shop['postcode'] . ' ' . $shop['city']);
}

/** Values for the {{name}} placeholders in cms/*.html. */
function placeholders(array $values): array
{
    $shop = $values['shop'];
    $delivery = $values['delivery'];
    $bank = $values['bank_transfer'];

    $carrierRows = '';
    foreach ($delivery['carriers'] as $carrier) {
        $carrierRows .= '<tr><td>' . e($carrier['name']) . '</td><td>' . e($carrier['time']) . '</td><td>'
            . price($carrier['fee']) . '</td></tr>';
    }

    return [
        '{{shop_name}}' => e($shop['name']),
        '{{shop_address}}' => e($shop['address1'] . ', ' . $shop['postcode'] . ' ' . $shop['city']),
        '{{shop_email}}' => e($shop['email']),
        '{{free_shipping_from}}' => price($delivery['free_from']),
        '{{max_weight}}' => e($delivery['max_weight_kg'] . ' kg'),
        '{{carriers_table}}' => '<table class="table table-bordered"><thead><tr><th>Forma dostawy</th>'
            . '<th>Czas dostawy</th><th>Koszt brutto</th></tr></thead><tbody>' . $carrierRows . '</tbody></table>',
        '{{bank_owner}}' => e($bank['owner']),
        '{{bank_name}}' => e($bank['bank']),
        '{{bank_account}}' => e($bank['account']),
    ];
}

function e(string $text): string
{
    return htmlspecialchars($text, ENT_QUOTES, 'UTF-8');
}

/** 2000 -> "2000 zł", 19.99 -> "19,99 zł" */
function price(float $amount): string
{
    $decimals = floor($amount) == $amount ? 0 : 2;

    return number_format($amount, $decimals, ',', '') . ' zł';
}

function pageContent(string $linkRewrite, array $placeholders): string
{
    $file = __DIR__ . '/cms/' . $linkRewrite . '.html';
    $html = strtr(file_get_contents($file), $placeholders);
    if (preg_match('/\{\{\w+\}\}/', $html, $unknown)) {
        throw new RuntimeException("Unknown placeholder {$unknown[0]} in $file");
    }

    return trim($html);
}

function findCmsPageId(string $linkRewrite): int
{
    return (int) Db::getInstance()->getValue(
        'SELECT id_cms FROM ' . _DB_PREFIX_ . 'cms_lang'
        . " WHERE link_rewrite = '" . pSQL($linkRewrite) . "'"
        . ' AND id_lang = ' . (int) Configuration::get('PS_LANG_DEFAULT')
    );
}

/** Creates or updates the CMS pages. Returns their IDs by link_rewrite. */
function saveCmsPages(array $placeholders): array
{
    $ids = [];
    $position = 0;
    foreach (CMS_PAGES as $linkRewrite => [$title, $description]) {
        $id = findCmsPageId($linkRewrite);
        $page = new CMS($id ?: null);
        $page->id_cms_category = 1; // root CMS category
        $page->active = true;
        $page->indexation = false; // noindex: the shop is never meant to be public
        $page->meta_title = forAllLanguages($title);
        $page->meta_description = forAllLanguages($description);
        $page->link_rewrite = forAllLanguages($linkRewrite);
        $page->content = forAllLanguages(pageContent($linkRewrite, $placeholders));
        mustSave($id ? $page->update() : $page->add(), "CMS page $linkRewrite");

        // add() always puts a new page last; set the order explicitly (used by the sitemap).
        Db::getInstance()->update('cms', ['position' => $position++], 'id_cms = ' . (int) $page->id);
        $ids[$linkRewrite] = (int) $page->id;
        say(($id ? 'Updated' : 'Created') . " CMS page \"$title\" (id {$page->id})");
    }

    return $ids;
}

function deleteDemoCmsPages(): void
{
    foreach (DEMO_CMS_PAGES as $linkRewrite) {
        $id = findCmsPageId($linkRewrite);
        if ($id) {
            mustSave((new CMS($id))->delete(), "deletion of CMS page $linkRewrite");
            say("Deleted demo CMS page $linkRewrite (id $id)");
        }
    }
}

/** Reuses the existing footer blocks in order, creates missing ones and deletes extra ones. */
function saveFooterBlocks(array $cmsIds): void
{
    $db = Db::getInstance();
    $idHook = (int) Hook::getIdByName('displayFooter');
    $existing = array_column($db->executeS(
        'SELECT id_link_block FROM ' . _DB_PREFIX_ . 'link_block'
        . " WHERE id_hook = $idHook ORDER BY position, id_link_block"
    ), 'id_link_block');

    foreach (FOOTER_BLOCKS as $position => $definition) {
        $id = (int) array_shift($existing);
        $block = new LinkBlock($id ?: null);
        $block->id_hook = $idHook;
        $block->position = $position;
        $block->name = forAllLanguages($definition['name']);
        $block->content = [
            'cms' => array_map(fn (string $linkRewrite) => $cmsIds[$linkRewrite], $definition['cms']),
            'product' => $definition['product'],
            'static' => $definition['static'],
            'category' => [],
        ];
        $block->custom_content = forAllLanguages('[]');
        mustSave($id ? $block->update() : $block->add(), 'footer block ' . $definition['name']);

        // The module orders blocks by link_block_shop.position, which add() and update() do not set.
        $db->update('link_block', ['position' => $position], 'id_link_block = ' . (int) $block->id);
        $db->update('link_block_shop', ['position' => $position], 'id_link_block = ' . (int) $block->id);
        say(($id ? 'Updated' : 'Created') . " footer block \"{$definition['name']}\"");
    }

    foreach ($existing as $extraId) {
        mustSave((new LinkBlock((int) $extraId))->delete(), "deletion of footer block $extraId");
        say("Deleted extra footer block (id $extraId)");
    }
}

function setPageTitles(): void
{
    foreach (PAGE_TITLES as $pageName => $title) {
        $meta = Meta::getMetaByPage($pageName, (int) Configuration::get('PS_LANG_DEFAULT'));
        $record = new Meta((int) $meta['id_meta']);
        $record->title = forAllLanguages($title);
        mustSave($record->update(), "title of page $pageName");
        say("Page \"$pageName\" title: $title");
    }
}

function disableDemoContent(): void
{
    foreach (DEMO_MODULES as $name) {
        if (Module::isEnabled($name)) {
            Module::getInstanceByName($name)->disable();
            say("Disabled demo module $name");
        }
    }

    // The installer adds five demo stores in Miami. They show on the "Sklepy" page, which the sitemap
    // still links to.
    $db = Db::getInstance();
    $db->update('store', ['active' => 0], 'active = 1');
    if ($db->Affected_Rows()) {
        say('Deactivated ' . $db->Affected_Rows() . ' demo stores');
    }
}

function setFormTexts(): void
{
    foreach (FORM_TEXTS as $key => $text) {
        Configuration::updateValue($key, forAllLanguages($text));
    }
    say('Form texts: ' . implode(', ', array_keys(FORM_TEXTS)));
}

try {
    setStoreDetails($values['shop']);
    $cmsIds = saveCmsPages(placeholders($values));
    Configuration::updateValue('PS_CONDITIONS_CMS_ID', $cmsIds[TERMS_PAGE]);
    deleteDemoCmsPages();
    saveFooterBlocks($cmsIds);
    setPageTitles();
    setFormTexts();
    disableDemoContent();
    // Rendered footer blocks and module output are cached as templates.
    Tools::clearAllCache();
    say('Shop content done');
} catch (Throwable $exception) {
    fwrite(STDERR, '[setup] FAILED: ' . $exception->getMessage() . PHP_EOL);
    exit(1);
}
