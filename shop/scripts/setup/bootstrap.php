<?php
// Shared start of the setup scripts in this folder (see docs/adr/0005-shop-data-set-by-php-setup-scripts.md).
// Loads PrestaShop, so the scripts can use its classes (CMS, Configuration, Module, ...).
// Run as www-data, otherwise cache files end up owned by root:
//   runuser -u www-data -- php /opt/ciocia/scripts/setup/<script>.php

if (PHP_SAPI !== 'cli') {
    exit(1);
}

require '/var/www/html/config/config.inc.php';

// HTMLPurifier checks CMS content on save and warns if its cache folder is missing, which it is
// right after sync-code.sh has deleted the cache.
if (!is_dir(_PS_CACHE_DIR_ . 'purifier')) {
    mkdir(_PS_CACHE_DIR_ . 'purifier', 0775, true);
}

/**
 * The same text for every installed language. The shop is Polish only, but the installer also adds
 * English; giving it the Polish text keeps installer English out of the shop.
 */
function forAllLanguages(string $text): array
{
    $values = [];
    foreach (Language::getIDs(false) as $idLang) {
        $values[(int) $idLang] = $text;
    }

    return $values;
}

function say(string $message): void
{
    echo '[setup] ' . $message . PHP_EOL;
}

/** Throws if PrestaShop refused to save an object (validation error, database error). */
function mustSave(bool $saved, string $what): void
{
    if (!$saved) {
        throw new RuntimeException('Could not save ' . $what);
    }
}
