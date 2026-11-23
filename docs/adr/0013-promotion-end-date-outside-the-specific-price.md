# 0013. Promotion end date kept outside the specific price

- Status: Accepted
- Date: 2026-11-23
- Authors: Jakub Rachubka

## Context

The source's product cards show when a promotion ends: "Cena przed: 23,94 zł · do 14.11.2026" (issue #111). The
date is `to` of the product's specific price in the `data-product` JSON, and the scraper now saves it as `promo_end`.

The source runs short promotions. In our scraped data 167 of 171 promotions end on 14.11.2026, which had already
passed when this was decided; the live source had moved on to new promotions ending on 28.11.2026. PrestaShop stops
applying a specific price after its `to` date. D3 needs at least 20 products with a current promotion when the shop
is graded, and `check-catalog.sh` counts only promotions with no end or an end still to come. Our promotions are
written by the importer without "from" and "to" (ADR 0008, ADR 0011).

## Options considered

**Write the date to `to` of the specific price (what #111 first asked for).**

- Pro: PrestaShop's own field; the module already shows it on the product page; nothing new to explain.
- Con: almost every promotion ends at once (167 of 171 on the day of the import already), and the rest within weeks.
  The shop falls below D3's 20 promotions, and a fresh clone imported later has none.
- Con: re-scraping before the defence only moves the problem by a few weeks.

**Show no date at all (close #111 as a documented gap).**

- Pro: nothing to build, D3 safe.
- Con: the cards look less like the source (D1), and the scraped date is thrown away.

**Our own table in `ciociaomnibus`, written by the importer through our own API resource (chosen).**

- Pro: the promotion keeps no end, so D3 and the Omnibus rule (ADR 0011) work as before; the card shows the source's
  date as on the source.
- Pro: the importer stays on the Webservice API (ADR 0008): the module adds the resource `ciocia_promo_ends`
  (`CiociaPromoEnd`, hook `addWebserviceResources`), with its permission in `webservice.php` like the core resources.
- Con: a running promotion can show a date that has passed ("Promocja ważna do: 14.11.2026" on 23.11). That is the
  trade-off we accept: the date is the source's, from the day of the scrape.
- Con: a second place that describes a promotion, next to the specific price.

## Decision

- Table `ciocia_promo_end`: one row per product, or per combination for a product with variants
  (`id_product_attribute`), with `date_end`. The importer creates, updates or deletes it next to the promotion
  (`set_promo_end`); the specific price keeps `to` = `0000-00-00 00:00:00`.
- The module shows the date when the specific price has no `to` of its own: after the regular price on cards
  (`ciocia_short`) and as "Promocja ważna do" on the product page. The Omnibus lowest price never reads the table.
- A deleted product or combination deletes its rows (object hooks `actionObjectProductDeleteAfter` and
  `actionObjectCombinationDeleteAfter`), so back-office deletes are covered too.
- A missing table shows no date instead of breaking the Omnibus line.

## Consequences

- Promotions in our shop never end on their own; the dates on the cards are the source's dates from the scrape and
  may be in the past.
- A shop installed before this change needs `30-configure-shop.sh` and then `40-webservice.sh` re-run once (table,
  hooks, key permission). Until then the import stops at the start with a message naming them.
- `ciociamenu` clears the page cache when a date changes, like other catalogue changes.
- If a real end is ever wanted (a promotion added by hand in the back office), its `to` is shown as before: the
  table is read only when `to` is empty.
- "Reset" or uninstalling `ciociaomnibus` deletes the dates with the price history; the next import writes them again.
