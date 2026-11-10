# 0003. Crawl sources and category assignment

- Status: Proposed
- Date: 2026-11-10
- Authors: Jakub Bugnacki

## Context

The crawl (#10) has to find every product and every category of the source shop, and know which categories each
product belongs to. W3 requires at least 4 categories, each with at least 2 non-empty subcategories, and no empty
category in our shop. Everything goes through the polite client at 1 request per second, so every extra page costs a
second, and a full run already takes about 40 minutes.

Facts from [scraper-recon.md](../scraper-recon.md) and the saved pages:

- The sitemap lists 2167 products and 162 categories.
- A product page gives its default category and that category's breadcrumb (default category plus its ancestors),
  nothing else.
- Na prezent (458) and Nowości (50) are never a product's default category, so a product page never mentions them.
  Only their listings show which products are in them.
- A parent category's listing also shows the products of all its subcategories (Kosmetyki: 741 products, 62 pages).
- A category page is also page 1 of its listing, 12 products per page.

## Options considered

**Sitemap only.** URLs from the sitemap, categories from product pages.

- Pro: the fewest requests (about 2330).
- Con: Na prezent and Nowości end up empty, which fails the "no empty category" check.
- Con: a product that is in a second regular category is assigned only to its default one.

**Sitemap, plus page 1 of every listing, plus full listings of Na prezent and Nowości (chosen).**

- Pro: page 1 comes free with the category page that is downloaded anyway, so every category that has products gets at
  least some, even if they are not its products' default category.
- Pro: the two special categories get all their products, at the cost of one extra page per 12 products in them.
- Pro: a product that is on a listing but not in the sitemap is still found and downloaded.
- Con: a product in a second regular category is assigned to it only if it shows on page 1 of that listing.

**Sitemap plus full listings of every category.**

- Pro: every category assignment the source shop has.
- Con: parent listings repeat the products of their subcategories, so this is several hundred extra pages, most of
  them giving nothing new. Walking only leaf categories would cut that down, but still adds about 200 pages for
  assignments that the shop does not need.

**Listings only, no sitemap.**

- Pro: one source for both URLs and assignments.
- Con: misses products that are in no listing, and still needs full walks of every category.

## Decision

Use the sitemap for product and category URLs, keep the product URLs from page 1 of every category listing, and walk
the listings of Na prezent and Nowości to their last page. The list of fully walked categories is
`FULL_LISTING_CATEGORY_IDS` in `scraper/scraper/config.py`.

A product's `category_ids` are its page's categories (default category first, then the breadcrumb) followed by every
other category whose listing showed it, without duplicates. Products are identified by the number at the start of
their URL path, because the sitemap and a listing can link the same product with different URLs.

What was seen on each listing is kept in `scraper-results/listings.json`, together with the next page still to walk.
Resuming uses it, and it shows where each assignment came from.

## Consequences

- No category with products in the source shop should be empty. The crawl ends with a warning for any that is, so
  this is checked on every run, not assumed.
- Some products miss a secondary regular category beyond page 1 of its listing. If that matters later, add the
  category id to `FULL_LISTING_CATEGORY_IDS` and run the crawl again: the listing continues from where page 1 stopped.
- `products.jsonl` is the merged result. The import (D2) reads `category_ids` from it and does not need
  `listings.json`.
- The sitemap is downloaded again on every run (2 requests), so a resumed run also picks up products added to the
  source shop in the meantime.
