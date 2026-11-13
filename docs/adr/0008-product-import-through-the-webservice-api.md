# 0008. Product import through the Webservice API

- Status: Proposed
- Date: 2026-11-13
- Authors: Marcel Kiraga

## Context

D2 asks for a script that creates the categories and products from the scraped results through the PrestaShop
Webservice API, with images, prices, VAT rates, stock and weight, and that a second run updates without creating
duplicates. W3 needs the result: at least 1000 products matching the source, stock 0-10 with 5-20% at 0, no empty
category, and a clean clone with data in at most 15 minutes. D2 allows 30 minutes for 1000 products with images.

The data (`scraper-results/`): 160 categories (13 top-level, up to 4 levels), 2159 products, 76 brands, 4822 images,
171 promotions, VAT 23% (1881), 8% (228) and 5% (50). PR #79 gave the API one key limited to the resources the import
needs, reachable only inside the Compose network.

What a test install showed before the design was fixed:

- An update (PUT) replaces the whole record: fields left out are emptied, including the description and the VAT group.
- PrestaShop indexes a product for search when it is saved through the API (`Product::addWs`, `updateWs`).
- Two products saved at the same moment deadlock in MySQL inside that search indexing (HTTP 500, product half saved).
- PrestaShop's HTML cleaner (HTMLPurifier) rewrites every description on save: it drops unknown attributes, writes `&`
  as `&amp;` and removes embedded `data:` images. A description read back never equals the source HTML.
- The cleaner needs the folder `var/cache/prod/purifier`. `sync-code.sh` deletes `var/cache/prod` on every start, and
  without the folder every product save answered HTTP 500 although the product was saved.
- The API refuses a description with `<iframe>` (product 9536 embeds a YouTube video) unless iframes are allowed.
- The top menu (`ps_mainmenu`) points at category IDs, which the API cannot set and which differ between installs.
- One image upload takes about 0.35 s, because PrestaShop makes 5 thumbnail sizes from it; a product save about 0.1 s.

## Options considered

### Where the importer runs

- **A Python container on the Compose network (chosen).** The team knows Python from the scraper; the lecturer
  needs only Docker; Stage 2 runs the same image as a one-off service on the cluster.
- A script on the developer's machine: needs Python installed, and cannot reach the shop, which has no published
  port and blocks the API at the proxy.
- PHP inside the shop container: could skip the API, but D2 requires the API.

### How existing records are recognised on a second run

- Products: `reference` = the source product ID. Unique, visible in the back office, and the field is meant for it.
- Categories: the source URL slug is not unique (`masci` and `dla-mezczyzn` appear twice). **Name plus parent (chosen)**
  is unique in the data and visible in the back office. A hidden marker in another field would be harder to explain.
- Images: the product's own list of image IDs (`associations.images`) is compared with the number of images in the
  data. The API's image list endpoint was not usable (it answers with PHP warnings in JSON).
- Descriptions: compared by visible text (tags removed, entities decoded), because the cleaner changes the markup.
  Turning the cleaner off would keep the HTML identical, but it is a security setting of the whole shop.

### Weight

The source labels every weight `g`, but some values are kilograms (0.04 for a 10 ml bottle). Only 182 products have
a weight. Checked against the 110 product names that state a weight or volume:

| Rule | Off by more than 10x |
|---|---|
| Always grams | 23 |
| Below 1 means kilograms | 2 (a 1.187 kg lamp, a 1.3 kg candle holder) |
| **Below 5 with decimals means kilograms (chosen)** | 0 |

The remaining case is the kajal pencil, 2.7 g in the name and 30 g in the data, which is its weight in the box.

### Stock

The brief wants 0-10 for every product and 5-20% at 0, and a second run must not change it. Random numbers would
change on every run. The stock is derived from the source ID: `h` = the first 8 bytes of SHA-256 of the ID as a
number; `h % 10 == 0` gives 0, otherwise `1 + (h // 10) % 10` gives 1-10. On the data this is 10.7% at 0. Using the
raw ID instead of its hash also passes (10.1%), but products added together have neighbouring IDs, so zeros could
cluster; the hash spreads them. Python's `hash()` is not used: it changes every time Python starts.

### Top menu

- Give the key the `configurations` resource: opens the whole configuration, including the SMTP password, to the key.
- A setup script run with `docker compose exec` after the import: a container cannot run `exec` in another one, so
  the one-command init (#71) would need a host script.
- **A small module, `ciociamenu` (chosen):** it listens to category events, which fire for API requests too, and points
  the menu at the top-level categories named in `shop/config/shop-settings.php` after every change.

### Speed

Sequentially the import would take about 35 minutes, most of it image uploads. Measured on the test install
(Docker with 12 CPUs):

| Approach | Full import |
|---|---|
| One thread per product doing everything, 4 workers, product saves under a lock | 744 s |
| The same with 8 workers | 642 s |
| **Two phases, 8 workers (chosen)** | MEASURED |

A product save alone takes 0.07 s; uploads scale from 2.6 images/s alone to 12.4/s with 8 at a time and 14/s
with 12. With everything mixed, uploads slowed the saves down, and the saves are serialised by the lock (because of
the deadlock in search indexing), so they held everything up. The chosen approach first saves every product with
its stock and promotion, then uploads all images, both with a thread pool of 8 workers (`--workers`).

## Decision

- The importer is a Python 3.12 package in `deploy/importer/`, run as the Compose service `importer` in the `init`
  profile: `docker compose -f deploy/compose.yaml --profile init run --rm importer`. It reads `scraper-results/`
  mounted read-only and writes its log to `deploy/logs/`.
- It validates every record against `scraper-results/schema.json` and rejects invalid ones with the reason in the log.
- Steps in order: read the shop once; categories, parents first; brands as manufacturers; products with their stock
  and promotion; their images; on a full run, delete products, categories and manufacturers that are not in the data
  (the installer's demo catalogue). Each step creates, updates or leaves a record alone, comparing with what the shop
  has.
- Updates always send the complete set of fields the importer manages.
- Prices: net = gross / (1 + VAT), 6 decimals, which gives back every source price to the grosz (unit test on all
  products). The VAT group is the active group whose only rate is the product's rate, found through the API.
- Promotions: one specific price per discounted product, an amount with tax included, so the shop shows exactly the
  source's promotional price.
- Weight and stock: the rules above, in `importer/mapping.py` with unit tests.
- Shop side: `sync-code.sh` recreates `var/cache/prod/purifier` after clearing the cache; `shop-settings.php` gets a
  `catalog` section (menu categories, out-of-stock orders denied, iframes allowed) applied by `configure-shop.php`,
  which also installs `ciociamenu`; `php.ini` sets `zend.exception_ignore_args = On`, because a crash inside the API
  wrote the first 15 characters of the key into the container log as a stack trace argument.

## Consequences

- A full import on a fresh shop takes MEASURED (4 workers); a second run takes MEASURED and reports 0 created.
- Renaming a category in the back office makes the next import create it again under the old name. The importer owns
  the catalogue: change products and categories in the data, not in the back office.
- A product whose images change but keep the same count is not re-uploaded. Changing an image means deleting the
  product's images in the back office, or changing the count.
- A product's markup changes on the source that keep the visible text the same are not carried over.
- The weight rule would read a future item such as a 7.5 kg one written as `7.5` as grams; the unit tests list the
  known cases.
- #71 builds the one-command init around this service; #72 (Omnibus) starts from the specific prices; #73 (variants)
  adds its resources to `PERMISSIONS` in `shop/scripts/setup/webservice.php`.
- Stage 2: the Host header is `SHOP_DOMAIN` (default `localhost:<HTTPS_PORT>`), so the same image works with the
  cluster's domain. Traffic between Swarm nodes is not encrypted by default; that is decided with the cluster setup.
