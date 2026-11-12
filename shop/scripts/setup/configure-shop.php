<?php
/**
 * Configures the shop for Poland (issue #47): currency, country, VAT, payments, carriers,
 * free delivery, e-mail and invoices, plus the promo code (issue #44). Values come from
 * shop/config/shop-settings.php.
 *
 * Runs once after the automatic install (post-install/30-configure-shop.sh). It is idempotent,
 * so it can also be run again by hand on a running shop:
 *   docker compose -f deploy/compose.yaml exec shop runuser -u www-data -- \
 *       php /opt/ciocia/scripts/setup/configure-shop.php
 */

use PrestaShop\PrestaShop\Adapter\SymfonyContainer;
use PrestaShop\PrestaShop\Core\Domain\Currency\Command\AddCurrencyCommand;

if (PHP_SAPI !== 'cli') {
    exit(1);
}

$shopDir = getenv('SHOP_DIR') ?: '/var/www/html';
$settingsFile = getenv('SHOP_SETTINGS') ?: '/opt/ciocia/config/shop-settings.php';

require $shopDir . '/config/config.inc.php';

// The Symfony container is needed to add a currency the way the back office does it
global $kernel;
$kernel = new AppKernel('prod', false);
$kernel->boot();

$settings = require $settingsFile;

configureCurrencies($settings);
configureCountry($settings['country_default']);
configureTaxes();
$carrierReferences = configureCarriers($settings);
configureShipping($settings);
configurePayments($settings, $carrierReferences);
configureMail($settings['mail']);
configureInvoices();
configurePromoCode($settings['promo_code']);

Tools::clearSmartyCache();
Cache::clear();
echo "Shop configuration done.\n";

/**
 * PLN as the default currency, extra currencies at a fixed rate, every other currency disabled.
 */
function configureCurrencies(array $settings)
{
    $rates = [$settings['currency_default'] => 1.0] + $settings['currencies_extra'];

    foreach ($rates as $iso => $rate) {
        if (!Currency::getIdByIsoCode($iso, 0, true)) {
            $commandBus = SymfonyContainer::getInstance()->get('prestashop.core.command_bus');
            $commandBus->handle(new AddCurrencyCommand($iso, (float) $rate, true));
            Cache::clear();
            echo "Currency $iso added.\n";
        }
    }

    $idDefault = (int) Currency::getIdByIsoCode($settings['currency_default'], 0, true);
    Configuration::updateValue('PS_CURRENCY_DEFAULT', $idDefault);

    $currencies = Db::getInstance()->executeS(
        'SELECT id_currency, iso_code FROM ' . _DB_PREFIX_ . 'currency WHERE deleted = 0'
    );
    foreach ($currencies as $row) {
        $currency = new Currency((int) $row['id_currency']);
        $wanted = isset($rates[$row['iso_code']]);
        $currency->active = $wanted;
        if ($wanted) {
            $currency->conversion_rate = (float) $rates[$row['iso_code']];
        }
        $currency->update();
    }
    echo 'Currencies: default ' . $settings['currency_default'] . ', active ' . implode(', ', array_keys($rates)) . ".\n";
}

/**
 * Only the default country is active, with the Polish address format (no state, postcode NN-NNN).
 */
function configureCountry($iso)
{
    $idCountry = (int) Country::getByIso($iso);

    $country = new Country($idCountry);
    $country->active = true;
    $country->contains_states = false;
    $country->need_zip_code = true;
    $country->zip_code_format = 'NN-NNN';
    $country->update();

    Db::getInstance()->update('country', ['active' => 0], 'id_country != ' . $idCountry);

    Configuration::updateValue('PS_COUNTRY_DEFAULT', $idCountry);
    Configuration::updateValue('PS_SHOP_COUNTRY_ID', $idCountry);
    Configuration::updateValue('PS_LOCALE_COUNTRY', strtolower($iso));
    // Do not switch the country by the browser language
    Configuration::updateValue('PS_DETECT_COUNTRY', 0);
    echo "Country: $iso is the only active country.\n";
}

/**
 * Polish VAT groups (23, 8, 5, 0 %) from PrestaShop's Polish localization pack; prices shown gross.
 */
function configureTaxes()
{
    if (!getTaxRulesGroupIdByRate(23)) {
        // Install made without the Polish pack (PS_COUNTRY was "PL" instead of "pl"): import its taxes
        $pack = new LocalizationPack();
        $pack->loadLocalisationPack(file_get_contents(_PS_ROOT_DIR_ . '/localization/pl.xml'), ['taxes']);
        echo "Polish VAT groups imported.\n";
    }

    Db::getInstance()->update('tax_rules_group', ['active' => 1], 'deleted = 0 AND name LIKE "PL %"');
    Configuration::updateValue('PS_TAX', 1);
    Configuration::updateValue('PS_TAX_DISPLAY', 1);
    // 0 = prices with tax, for every customer group
    Db::getInstance()->update('group', ['price_display_method' => 0]);
    Configuration::updateValue('PS_WEIGHT_UNIT', 'kg');
    echo "Taxes: Polish VAT groups active, prices shown gross.\n";
}

/**
 * Tax rules group whose rule for the default country has the given rate, or 0.
 */
function getTaxRulesGroupIdByRate($rate)
{
    return (int) Db::getInstance()->getValue(
        'SELECT g.id_tax_rules_group FROM ' . _DB_PREFIX_ . 'tax_rules_group g
        JOIN ' . _DB_PREFIX_ . 'tax_rule r ON r.id_tax_rules_group = g.id_tax_rules_group
        JOIN ' . _DB_PREFIX_ . 'tax t ON t.id_tax = r.id_tax
        WHERE g.deleted = 0 AND r.id_country = ' . (int) Country::getByIso('PL') . '
            AND t.rate = ' . (float) $rate . '
        ORDER BY g.id_tax_rules_group'
    );
}

/**
 * Our carriers, priced by weight; out of range = carrier not offered. Other carriers are deleted.
 * Returns the id_reference of each of our carriers.
 */
function configureCarriers(array $settings)
{
    $idLang = (int) Configuration::get('PS_LANG_DEFAULT');
    $idZone = (int) Country::getIdZone((int) Country::getByIso($settings['country_default']));
    $idTaxGroup = getTaxRulesGroupIdByRate($settings['shipping_vat']);
    $groupIds = array_column(Group::getGroups($idLang), 'id_group');
    $references = [];

    foreach ($settings['carriers'] as $name => $config) {
        $idCarrier = (int) Db::getInstance()->getValue(
            'SELECT id_carrier FROM ' . _DB_PREFIX_ . 'carrier WHERE deleted = 0 AND name = "' . pSQL($name) . '"'
        );
        $carrier = new Carrier($idCarrier ?: null);
        $carrier->name = $name;
        $carrier->delay = [$idLang => $config['delay']];
        $carrier->active = true;
        $carrier->is_free = false;
        $carrier->shipping_handling = false;
        $carrier->shipping_external = false;
        $carrier->need_range = true;
        $carrier->shipping_method = Carrier::SHIPPING_METHOD_WEIGHT;
        // Cart outside every range: the carrier is not offered (instead of using the last range)
        $carrier->range_behavior = 1;
        $carrier->max_weight = (float) max(array_keys($config['ranges']));
        $idCarrier ? $carrier->update() : $carrier->add();
        // Reload: add() sets id_reference in the database only
        $carrier = new Carrier((int) $carrier->id);

        if (!$carrier->getZone($idZone)) {
            $carrier->addZone($idZone);
        }
        $carrier->setGroups($groupIds);
        $carrier->setTaxRulesGroup($idTaxGroup);
        setCarrierPrices($carrier, $idZone, $config['ranges'], $settings['shipping_vat']);

        $references[] = (int) $carrier->id_reference;
        echo "Carrier $name: " . count($config['ranges']) . ' weight ranges up to ' . (float) $carrier->max_weight . " kg.\n";
    }

    // Delete the installer's demo carriers (and any other carrier not in the settings)
    $names = array_map('pSQL', array_keys($settings['carriers']));
    Db::getInstance()->update(
        'carrier',
        ['active' => 0, 'deleted' => 1],
        'deleted = 0 AND name NOT IN ("' . implode('","', $names) . '")'
    );

    $idDefault = (int) Db::getInstance()->getValue(
        'SELECT id_carrier FROM ' . _DB_PREFIX_ . 'carrier WHERE deleted = 0 AND id_reference = ' . $references[0]
    );
    Configuration::updateValue('PS_CARRIER_DEFAULT', $idDefault);

    return $references;
}

/**
 * Weight ranges and their fees: "up to N kg => gross fee". Stored net, because the carrier adds VAT.
 */
function setCarrierPrices(Carrier $carrier, $idZone, array $ranges, $vat)
{
    $db = Db::getInstance();
    $keep = [];
    $from = 0.0;

    ksort($ranges);
    foreach ($ranges as $to => $grossFee) {
        $where = 'id_carrier = ' . (int) $carrier->id
            . ' AND delimiter1 = ' . (float) $from . ' AND delimiter2 = ' . (float) $to;
        $idRange = (int) $db->getValue('SELECT id_range_weight FROM ' . _DB_PREFIX_ . 'range_weight WHERE ' . $where);
        if (!$idRange) {
            $range = new RangeWeight();
            $range->id_carrier = (int) $carrier->id;
            $range->delimiter1 = $from;
            $range->delimiter2 = (float) $to;
            // add() also creates a 0 PLN price in each zone of the carrier; it is replaced below
            $range->add();
            $idRange = (int) $range->id;
        }
        $keep[] = $idRange;

        $netFee = round($grossFee / (1 + $vat / 100), 6);
        $priceWhere = 'id_carrier = ' . (int) $carrier->id . ' AND id_range_weight = ' . $idRange
            . ' AND id_zone = ' . (int) $idZone;
        if ($db->getValue('SELECT id_delivery FROM ' . _DB_PREFIX_ . 'delivery WHERE ' . $priceWhere)) {
            $db->update('delivery', ['price' => $netFee], $priceWhere);
        } else {
            $db->insert('delivery', [
                'id_carrier' => (int) $carrier->id,
                'id_range_weight' => $idRange,
                'id_zone' => (int) $idZone,
                'price' => $netFee,
            ]);
        }
        $from = (float) $to;
    }

    // Ranges no longer in the settings
    $old = 'id_carrier = ' . (int) $carrier->id . ' AND id_range_weight NOT IN (' . implode(',', $keep) . ')';
    $db->delete('delivery', $old);
    $db->delete('range_weight', $old);
}

function configureShipping(array $settings)
{
    Configuration::updateValue('PS_SHIPPING_FREE_PRICE', (float) $settings['free_shipping_from']);
    Configuration::updateValue('PS_SHIPPING_FREE_WEIGHT', 0);
    Configuration::updateValue('PS_SHIPPING_HANDLING', 0);
    Configuration::updateValue('PS_SHIPPING_METHOD', 1);
    echo 'Free delivery from ' . $settings['free_shipping_from'] . " PLN gross.\n";
}

/**
 * Bank transfer and cash on delivery, for every active currency (PLN and EUR, so checkout works
 * after switching currency in the header), the default country and our carriers.
 * Cheque is uninstalled: it is not used in Poland.
 */
function configurePayments(array $settings, array $carrierReferences)
{
    $checkPayment = Module::getInstanceByName('ps_checkpayment');
    if ($checkPayment && Module::isInstalled('ps_checkpayment')) {
        $checkPayment->uninstall();
        echo "Payment ps_checkpayment uninstalled.\n";
    }

    Configuration::updateValue('BANK_WIRE_OWNER', $settings['bank_wire']['owner']);
    Configuration::updateValue('BANK_WIRE_DETAILS', $settings['bank_wire']['details']);
    Configuration::updateValue('BANK_WIRE_ADDRESS', $settings['bank_wire']['address']);

    $db = Db::getInstance();
    $idShop = (int) Configuration::get('PS_SHOP_DEFAULT');
    $currencyIds = [];
    foreach (array_merge([$settings['currency_default']], array_keys($settings['currencies_extra'])) as $iso) {
        $currencyIds[] = (int) Currency::getIdByIsoCode($iso, 0, true);
    }
    $idCountry = (int) Country::getByIso($settings['country_default']);

    foreach (['ps_wirepayment', 'ps_cashondelivery'] as $name) {
        if (!Module::isInstalled($name)) {
            Module::getInstanceByName($name)->install();
        }
        $module = Module::getInstanceByName($name);
        $module->enable();
        $idModule = (int) $module->id;
        $where = 'id_module = ' . $idModule . ' AND id_shop = ' . $idShop;

        $db->delete('module_currency', $where);
        foreach ($currencyIds as $idCurrency) {
            $db->insert('module_currency', ['id_module' => $idModule, 'id_shop' => $idShop, 'id_currency' => $idCurrency]);
        }

        $db->delete('module_country', $where);
        $db->insert('module_country', ['id_module' => $idModule, 'id_shop' => $idShop, 'id_country' => $idCountry]);

        $db->delete('module_carrier', $where);
        foreach ($carrierReferences as $reference) {
            $db->insert('module_carrier', ['id_module' => $idModule, 'id_shop' => $idShop, 'id_reference' => $reference]);
        }
        echo "Payment $name: enabled.\n";
    }
}

function configureMail(array $mail)
{
    Configuration::updateValue('PS_MAIL_METHOD', 2); // 2 = SMTP
    Configuration::updateValue('PS_MAIL_SERVER', $mail['server']);
    Configuration::updateValue('PS_MAIL_SMTP_PORT', (int) $mail['port']);
    Configuration::updateValue('PS_MAIL_SMTP_ENCRYPTION', 'off');
    Configuration::updateValue('PS_MAIL_USER', '');
    Configuration::updateValue('PS_MAIL_PASSWD', '');
    Configuration::updateValue('PS_CUSTOMER_CREATION_EMAIL', 1);
    echo 'E-mail: SMTP to ' . $mail['server'] . ':' . $mail['port'] . ".\n";

    // The installer writes mails/pl before the Polish translations are loaded, so the e-mail body
    // comes out in English. Generate the templates again from the installed translations.
    $theme = Configuration::get('PS_MAIL_THEME');
    $locale = (new Language((int) Configuration::get('PS_LANG_DEFAULT')))->locale;
    $command = 'php ' . escapeshellarg(_PS_ROOT_DIR_ . '/bin/console') . ' prestashop:mail:generate '
        . escapeshellarg($theme) . ' ' . escapeshellarg($locale) . ' --overwrite=true --env=prod --no-debug --quiet';
    exec($command, $output, $exitCode);
    if ($exitCode !== 0) {
        throw new RuntimeException("Generating e-mail templates failed: $command");
    }
    echo "E-mail templates generated in $locale.\n";
}

/**
 * Invoices on. A cash on delivery order gets its invoice at once, so the customer can download it
 * from the order history (E2E step 10) without the order status being changed in the back office.
 */
function configureInvoices()
{
    Configuration::updateValue('PS_INVOICE', 1);
    Db::getInstance()->update(
        'order_state',
        ['invoice' => 1],
        'id_order_state = ' . (int) Configuration::get('PS_OS_COD_VALIDATION')
    );
    echo "Invoices: enabled, issued for cash on delivery orders.\n";
}

/**
 * The promo code as a cart rule: a percentage off the products, once per customer, valid for ten
 * years from the last run. Found by its code, so a second run updates it instead of adding another.
 * PrestaShop shows the promo code field in the cart and checkout only while a cart rule exists.
 */
function configurePromoCode(array $promo)
{
    $idLang = (int) Configuration::get('PS_LANG_DEFAULT');
    $rule = new CartRule((int) CartRule::getIdByCode($promo['code']) ?: null);
    $rule->name = [$idLang => $promo['name']];
    $rule->code = $promo['code'];
    $rule->reduction_percent = (float) $promo['percent'];
    $rule->date_from = date('Y-m-d 00:00:00');
    $rule->date_to = date('Y-m-d 23:59:59', strtotime('+10 years'));
    $rule->quantity = 1000000;
    $rule->quantity_per_user = 1;
    // Not listed under "Take advantage of our exclusive offers": the code is entered by hand.
    $rule->highlight = false;
    $rule->active = true;
    $rule->id ? $rule->update() : $rule->add();
    echo 'Promo code ' . $promo['code'] . ': ' . $promo['percent'] . "% off the products, once per customer.\n";
}
