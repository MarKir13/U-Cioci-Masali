# 0008. Omnibus price from our own module with a price history in the database

- Status: Proposed
- Date: 2026-11-13
- Authors: Mateusz Radziul

## Context

D3 requires at least 20 products with a price promotion, and every promotion must show the lowest price from the
30 days before the discount (EU Omnibus directive). The import ([Data 2/3], #70) adds 171 promotions as specific
prices, most likely without a "from" date. Prices also change in the back office, and the acceptance criteria of #72
check exactly that: change a price, add a promotion, and the line must show the lowest price from before it.

PrestaShop 8.2.8 does not show this price: nothing in the core or in the bundled modules mentions it. Paid modules
are not allowed (AGENTS.md rule 11). Whatever we choose must survive `down` and `up`, a clean install from the
README, and Stage 2, where several shop containers run against one database.

## Options considered

**A ready free module.** The one we found, `DesignCart/dc_ps_omnibus`, was rejected:

- it takes the lowest price of the last 30 days from today, not from before the promotion, and it logs the
  promotion price itself, so after a promotion is added it shows the current promotion price;
- it keeps the history in files in its own module folder. `sync-code.sh` replaces that folder on every start, so the
  history would be lost on every restart; on the cluster each container would have its own files, and a database
  backup (D4) would not include them;
- it shows the line on the product page only, while #72 also needs it in product lists;
- it has no licence, so we may not copy it into the repository.

**No history: show the regular price as the lowest price.** Simple, and right after the import it is even correct.
It is wrong as soon as a price changes before a promotion, which is the back-office scenario from #72.

**Our own module with the history in database tables, written by PrestaShop's object hooks (chosen).**

- Pro: the history is in the shop database, so it survives restarts, is shared by every container, and is in every
  database backup.
- Pro: the object hooks (`actionObjectProductUpdateAfter`, `actionObjectSpecificPriceAddAfter`, ...) run for every
  save through PrestaShop's classes: the back office (including the new product page, which saves through
  `ObjectModel`), the Webservice API used by our import, and the setup scripts.
- Pro: the rule is one plain PHP function with its own test, which runs in CI without PrestaShop.
- Con: changes that bypass PrestaShop's classes (direct SQL) are not seen.

## Decision

Module `shop/modules/ciociaomnibus`, installed by `configure-shop.php` (ADR 0005):

- `ciocia_price_history`: one row each time the gross price a visitor sees changes (default country and currency,
  visitor group, quantity 1, promotions included), per combination, or with `id_product_attribute` 0 for a product
  without combinations. Install and the setup script add a starting row with the regular price for every product
  that has none.
- `ciocia_promo_start`: when a promotion was added, for promotions without a "from" date.
- The rule (`CiociaOmnibusRule`): the start is the promotion's "from" date, or the saved start. The window is
  the 30 days before it. The answer is the lowest of the price in effect when the window opened and every price set
  inside it. Rows from the start on, including the promotion price itself, are not counted. With no row before the
  start, the regular price.
- Dates come from PHP with microseconds (`DATETIME(6)`), in the shop's time zone. MariaDB uses UTC, while promotion
  dates are saved in the shop's time zone, and a row saved in the same second as a promotion must still count as
  after it.
- Display: the child theme calls `displayProductPriceBlock` with our own type `omnibus_price` under the price in
  `catalog/_partials/product-prices.tpl` and `catalog/_partials/miniatures/product.tpl` (both extend Classic's
  templates). Classic's own types are not used: `old_price` is above the old price, and `unit_price` also runs in
  the cart.

## Consequences

- The line shows only for a product in a promotion, on the product page and on every product card (category,
  search, promotions, home page), and follows the selected combination.
- The importer (#70) must update a promotion in place on a second run. Deleting it and adding it again gives it a
  new start date, and the window would then hold the promotion price.
- A promotion scheduled for the future writes no row when it starts, because nothing saves anything then. Its price
  is missing from the history of a later promotion. Specific prices for all products (`id_product` 0) and for a
  single cart are ignored.
- "Reset" or uninstalling the module in the back office deletes the history.
- #75 and #76, which rewrite the product card and the product page, must keep the one hook line.
- The history grows by one row per price change, with no clean-up. That is small at our scale.
