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
// The same settings file as configure-shop.php (shop/config/shop-settings.php in the repository), so the
// pages describe the carriers, fees and payments the checkout really offers.
$settings = require getenv('SHOP_SETTINGS') ?: '/opt/ciocia/config/shop-settings.php';

// CMS pages in footer order: link_rewrite => [title, meta description].
// The page text is in cms/<link_rewrite>.html. {{name}} placeholders are filled in from the settings
// (see placeholders() below), {{link:<link_rewrite>}} becomes a link to that page with its title as
// the text (see cmsLinks()).
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

// The page linked from the free delivery note in the header (templates/_partials/header.tpl),
// stored as CIOCIA_DELIVERY_CMS_ID because page IDs differ between installs.
const DELIVERY_PAGE = 'dostawa';

// The page linked from the cookie notice (templates/_partials/cookie-notice.tpl),
// stored as CIOCIA_PRIVACY_CMS_ID for the same reason.
const PRIVACY_PAGE = 'polityka-prywatnosci';

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
    // Newsletter (module ps_emailsubscription): under the form in the footer and next to the checkbox in
    // registration. The installer's text points to the deleted legal notice page.
    'NW_CONDITIONS' => 'Wypiszesz się w każdej chwili — link znajdziesz w stopce każdego maila.',
];

// Contact form (module contactform, issue #45). The source form has only e-mail and message: the
// "Temat" select shows only with more than one contact, and "Załącznik" only with file upload on.
// The installer adds two contacts; the technical one is deleted.
const CONTACT_NAME = 'Biuro obsługi klienta';
const DELETED_CONTACTS = ['Webmaster'];

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
function placeholders(array $settings): array
{
    $store = $settings['store'];
    $bank = $settings['bank_wire'];

    // Fees by weight, as configure-shop.php sets them: one row per weight range, one column per carrier,
    // so the table stays narrow on phones. Carriers may have different ranges, so the rows use all limits.
    $carriers = $settings['carriers'];
    $limits = [];
    foreach ($carriers as $carrier) {
        $limits = array_merge($limits, array_keys($carrier['ranges']));
    }
    $limits = array_unique($limits);
    sort($limits);
    $maxWeight = end($limits);

    $header = '<th>Waga paczki</th>';
    $delays = '<th>Czas dostawy</th>';
    foreach ($carriers as $name => $carrier) {
        $header .= '<th>' . e($name) . '</th>';
        $delays .= '<td>' . e($carrier['delay']) . '</td>';
    }
    $rows = '<tr>' . $delays . '</tr>';
    $from = 0;
    foreach ($limits as $upTo) {
        // Braces are needed: PHP would read "$from–" (with the dash) as one variable name.
        $rows .= '<tr><th>' . e($from ? "{$from}–{$upTo} kg" : "do {$upTo} kg") . '</th>';
        foreach ($carriers as $carrier) {
            $rows .= '<td>' . feeUpTo($carrier['ranges'], $upTo) . '</td>';
        }
        $rows .= '</tr>';
        $from = $upTo;
    }

    return [
        '{{shop_name}}' => e($store['name']),
        '{{shop_address}}' => e($store['address1'] . ', ' . $store['postcode'] . ' ' . $store['city']),
        '{{shop_email}}' => e($store['email']),
        '{{free_shipping_from}}' => price($settings['free_shipping_from']),
        '{{max_weight}}' => e($maxWeight . ' kg'),
        '{{carriers_table}}' => '<table class="table table-bordered"><caption>Koszt dostawy brutto</caption>'
            . '<thead><tr>' . $header . '</tr></thead><tbody>' . $rows . '</tbody></table>',
        '{{bank_owner}}' => e($bank['owner']),
        '{{bank_account}}' => e($bank['details']),
        '{{bank_address}}' => e($bank['address']),
    ];
}

/** Fee of the first range that covers $weight, or "–" if the carrier does not take parcels that heavy. */
function feeUpTo(array $ranges, float $weight): string
{
    foreach ($ranges as $upTo => $fee) {
        if ($weight <= $upTo) {
            return price($fee);
        }
    }

    return '–';
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

/** Values for the {{link:<link_rewrite>}} placeholders: a link to that CMS page, with its title as the text. */
function cmsLinks(array $cmsIds): array
{
    $link = Context::getContext()->link;
    $idLang = (int) Configuration::get('PS_LANG_DEFAULT');
    $links = [];
    foreach ($cmsIds as $linkRewrite => $id) {
        // Only the path is stored, without the domain, so the links keep working when the shop runs under
        // another address (Stage 2 cluster).
        $url = parse_url($link->getCMSLink($id, null, null, $idLang));
        $href = $url['path'] . (isset($url['query']) ? '?' . $url['query'] : '');
        $links["{{link:$linkRewrite}}"] = '<a href="' . e($href) . '">' . e(CMS_PAGES[$linkRewrite][0]) . '</a>';
    }

    return $links;
}

function pageContent(string $linkRewrite, array $placeholders): string
{
    $file = __DIR__ . '/cms/' . $linkRewrite . '.html';
    $html = strtr(file_get_contents($file), $placeholders);
    if (preg_match('/\{\{[\w:-]+\}\}/', $html, $unknown)) {
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
    // Pages link to each other ({{link:...}}) and a link needs the page ID, so missing pages are created
    // first without text, and then every page gets its text.
    $ids = [];
    foreach (array_keys(CMS_PAGES) as $linkRewrite) {
        $ids[$linkRewrite] = findCmsPageId($linkRewrite);
        if (!$ids[$linkRewrite]) {
            $ids[$linkRewrite] = saveCmsPage(null, $linkRewrite, '');
            say("Created CMS page $linkRewrite (id {$ids[$linkRewrite]})");
        }
    }

    $placeholders += cmsLinks($ids);
    foreach ($ids as $linkRewrite => $id) {
        saveCmsPage($id, $linkRewrite, pageContent($linkRewrite, $placeholders));
        say('Saved CMS page "' . CMS_PAGES[$linkRewrite][0] . "\" (id $id)");
    }

    return $ids;
}

/** Saves one page of CMS_PAGES; a new page when $id is null. Returns the page ID. */
function saveCmsPage(?int $id, string $linkRewrite, string $content): int
{
    [$title, $description] = CMS_PAGES[$linkRewrite];
    $page = new CMS($id);
    $page->id_cms_category = 1; // root CMS category
    $page->active = true;
    $page->indexation = false; // noindex: the shop is never meant to be public
    $page->meta_title = forAllLanguages($title);
    $page->meta_description = forAllLanguages($description);
    $page->link_rewrite = forAllLanguages($linkRewrite);
    $page->content = forAllLanguages($content);
    mustSave($id ? $page->update() : $page->add(), "CMS page $linkRewrite");

    // add() always puts a new page last; set the order of CMS_PAGES explicitly (used by the sitemap).
    $position = array_search($linkRewrite, array_keys(CMS_PAGES), true);
    Db::getInstance()->update('cms', ['position' => $position], 'id_cms = ' . (int) $page->id);

    return (int) $page->id;
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

/** One contact that receives messages from the contact form, at the store e-mail, and no attachments. */
function setContactForm(array $shop): void
{
    Configuration::updateValue('PS_CUSTOMER_SERVICE_FILE_UPLOAD', 0);

    $idLang = (int) Configuration::get('PS_LANG_DEFAULT');
    foreach (Contact::getContacts($idLang) as $row) {
        if (in_array($row['name'], DELETED_CONTACTS, true)) {
            mustSave((new Contact((int) $row['id_contact']))->delete(), 'deletion of contact ' . $row['name']);
            say('Deleted contact ' . $row['name']);
        }
    }

    // After the deletion a fresh install has one contact left: customer service. Name it as on the source.
    $contacts = Contact::getContacts($idLang);
    if (!$contacts) {
        throw new RuntimeException('No contact left for the contact form; add one in the back office');
    }
    if (count($contacts) > 1) {
        say('Warning: ' . count($contacts) . ' contacts left, the contact form shows a subject select;'
            . ' only the customer service contact is renamed');
        $contacts = array_values(array_filter($contacts, fn (array $row) => (bool) $row['customer_service'])) ?: $contacts;
    }
    $contact = new Contact((int) $contacts[0]['id_contact']);
    $contact->name = forAllLanguages(CONTACT_NAME);
    $contact->email = $shop['email'];
    $contact->customer_service = true;
    mustSave($contact->update(), 'contact ' . CONTACT_NAME);
    say('Contact form: "' . CONTACT_NAME . '" <' . $shop['email'] . '>, no attachments');
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
    setStoreDetails($settings['store']);
    $cmsIds = saveCmsPages(placeholders($settings));
    Configuration::updateValue('PS_CONDITIONS_CMS_ID', $cmsIds[TERMS_PAGE]);
    Configuration::updateValue('CIOCIA_DELIVERY_CMS_ID', $cmsIds[DELIVERY_PAGE]);
    Configuration::updateValue('CIOCIA_PRIVACY_CMS_ID', $cmsIds[PRIVACY_PAGE]);
    deleteDemoCmsPages();
    saveFooterBlocks($cmsIds);
    setContactForm($settings['store']);
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
