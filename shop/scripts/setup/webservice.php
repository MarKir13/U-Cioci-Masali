<?php
// Turns on the PrestaShop Webservice API and sets up the importer's key (issue #69), with access to
// only the resources the import needs (D2).
//
// Runs once after the automatic install (post-install/40-webservice.sh). Safe to run again, for example
// after changing PS_WEBSERVICE_KEY in deploy/.env (then `up -d` first, so the container gets the new value):
//   docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/40-webservice.sh
// The key is found by its description, so a second run updates it in place and never adds another one.
//
// How the importer reaches the API: plain HTTP inside the Compose network, http://shop/api/<resource>,
// with the key as the HTTP Basic auth user and an empty password, and with the two headers the proxy
// sends for every browser request:
//   Host: localhost:<HTTPS_PORT>   Required. PrestaShop answers any other host (such as "shop") with
//                                  302 to its own domain (PS_DOMAIN), tested on a fresh install.
//   X-Forwarded-Proto: https       Not needed by the API (the same 200 and the same https links without
//                                  it), sent anyway so the request is the same as one from the proxy.
// The proxy answers 404 for /api/ and /webservice/, so the API cannot be reached from outside Docker.
// Never send the key as ?ws_key=...: Apache writes every URL to its access log, but not the auth header.
// The /api/ rewrite rule is always in PrestaShop's generated .htaccess, so it needs no extra setup.

require __DIR__ . '/bootstrap.php';

// Finds our key on a re-run. Shown in the back office under Advanced Parameters > Webservice.
const KEY_DESCRIPTION = 'ciocia-importer';

// What the importer may do, per API resource. Everything not listed here (customers, addresses, orders,
// carts, employees, configurations, ...) is refused with 401.
// The variants issue (#73) adds combinations, product_options and product_option_values.
const PERMISSIONS = [
    // Read and write. DELETE because the import removes the installer's demo products and categories,
    // and replaces specific prices.
    'categories' => ['GET', 'HEAD', 'POST', 'PUT', 'DELETE'],
    'products' => ['GET', 'HEAD', 'POST', 'PUT', 'DELETE'],
    'images' => ['GET', 'HEAD', 'POST', 'PUT', 'DELETE'],
    'specific_prices' => ['GET', 'HEAD', 'POST', 'PUT', 'DELETE'],
    // PrestaShop creates the stock row together with the product, so the import only updates it.
    'stock_availables' => ['GET', 'HEAD', 'PUT'],
    // Read only: the tax rule group for a VAT rate is found through group -> rule -> tax (rate),
    // and the Polish language ID through languages.
    'tax_rule_groups' => ['GET', 'HEAD'],
    'tax_rules' => ['GET', 'HEAD'],
    'taxes' => ['GET', 'HEAD'],
    'languages' => ['GET', 'HEAD'],
];

/** The key from the container environment (deploy/.env). Never printed, not even when it is invalid. */
function keyFromEnvironment(): string
{
    $key = (string) getenv('PS_WEBSERVICE_KEY');
    if (!preg_match('/^[A-Z0-9]{32}$/', $key)) {
        throw new RuntimeException('PS_WEBSERVICE_KEY must be exactly 32 characters, only A-Z and 0-9 (see deploy/.env.example)');
    }

    return $key;
}

/** Stops on a resource name PrestaShop does not know. setPermissionForAccount() would skip it silently. */
function checkResourceNames(): void
{
    $unknown = array_diff(array_keys(PERMISSIONS), array_keys(WebserviceRequest::getResources()));
    if ($unknown) {
        throw new RuntimeException('Unknown API resources in PERMISSIONS: ' . implode(', ', $unknown));
    }
}

/**
 * Creates our key or updates it, and returns [account ID, what happened].
 *
 * Plain SQL instead of WebserviceKey::add(): add() writes "Webservice key created: <key>" to PrestaShop's
 * log (table ps_log, Advanced Parameters > Logs), and the key must appear in no log. Database errors are
 * replaced by a general message, because PrestaShop's database errors can contain the SQL with the key.
 */
function saveKey(string $key): array
{
    $db = Db::getInstance();
    $table = _DB_PREFIX_ . 'webservice_account';

    try {
        $sameKeyElsewhere = (int) $db->getValue('SELECT id_webservice_account FROM `' . $table . '`'
            . ' WHERE `key` = "' . pSQL($key) . '" AND description <> "' . pSQL(KEY_DESCRIPTION) . '"');
        $existing = $db->getRow('SELECT id_webservice_account, `key`, active FROM `' . $table . '`'
            . ' WHERE description = "' . pSQL(KEY_DESCRIPTION) . '"');
    } catch (Throwable $exception) {
        throw new RuntimeException('Could not read the webservice keys (database error)');
    }
    if ($sameKeyElsewhere) {
        throw new RuntimeException('Another webservice account already uses this key (ID ' . $sameKeyElsewhere . ')');
    }

    try {
        if (!$existing) {
            $saved = $db->insert('webservice_account', [
                'key' => pSQL($key),
                'description' => pSQL(KEY_DESCRIPTION),
                'class_name' => 'WebserviceRequest',
                'is_module' => 0,
                'active' => 1,
            ]);
            $id = (int) $db->Insert_ID();
            $status = 'created';
        } else {
            $id = (int) $existing['id_webservice_account'];
            $changed = $existing['key'] !== $key || !$existing['active'];
            $saved = !$changed || $db->update(
                'webservice_account',
                ['key' => pSQL($key), 'active' => 1],
                'id_webservice_account = ' . $id
            );
            $status = $changed ? 'updated' : 'unchanged';
        }
        // The API refuses a key that is not linked to the shop (403). INSERT IGNORE: the link may exist.
        foreach (Shop::getShops(false, null, true) as $idShop) {
            $saved = $saved && $db->insert(
                'webservice_account_shop',
                ['id_webservice_account' => $id, 'id_shop' => (int) $idShop],
                false,
                true,
                Db::INSERT_IGNORE
            );
        }
    } catch (Throwable $exception) {
        $saved = false;
    }
    mustSave($saved && $id > 0, 'the webservice key (database error)');

    return [$id, $status];
}

/** Sets the key's permissions to exactly PERMISSIONS. Returns false when they already were. */
function savePermissions(int $idAccount): bool
{
    $current = [];
    $rows = Db::getInstance()->executeS('SELECT resource, method FROM `' . _DB_PREFIX_ . 'webservice_permission`'
        . ' WHERE id_webservice_account = ' . $idAccount);
    foreach ($rows ?: [] as $row) {
        $current[] = $row['resource'] . ' ' . $row['method'];
    }

    // setPermissionForAccount() takes [resource => [method => anything]]
    $wanted = [];
    $toSet = [];
    foreach (PERMISSIONS as $resource => $methods) {
        foreach ($methods as $method) {
            $wanted[] = $resource . ' ' . $method;
            $toSet[$resource][$method] = 'on';
        }
    }

    sort($current);
    sort($wanted);
    if ($current === $wanted) {
        return false;
    }
    // Deletes the account's old permissions, then inserts the new ones
    mustSave(WebserviceKey::setPermissionForAccount($idAccount, $toSet), 'the webservice permissions');

    return true;
}

try {
    $key = keyFromEnvironment();
    checkResourceNames();

    $wasOn = (bool) Configuration::get('PS_WEBSERVICE');
    mustSave(Configuration::updateValue('PS_WEBSERVICE', 1), 'PS_WEBSERVICE');
    say('Webservice API ' . ($wasOn ? 'already on' : 'turned on'));

    [$idAccount, $status] = saveKey($key);
    say('Key "' . KEY_DESCRIPTION . '" (ID ' . $idAccount . ') ' . $status . ' from PS_WEBSERVICE_KEY');

    $permissionsChanged = savePermissions($idAccount);
    say('Permissions ' . ($permissionsChanged ? 'set' : 'unchanged') . ': ' . implode(', ', array_keys(PERMISSIONS)));
} catch (Throwable $exception) {
    fwrite(STDERR, '[setup] FAILED: ' . $exception->getMessage() . PHP_EOL);
    exit(1);
}
