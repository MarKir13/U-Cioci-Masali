# 0005. Products left out on purpose, and publishing the images

- Status: Proposed
- Date: 2026-11-11
- Authors: Jakub Bugnacki

## Context

The full crawl (#12) found 2182 products. W2 allows no product without a name, price, description or image, and W3
requires that every category has products and that the data matches the source shop. 23 products did not fit:

- 17 have no description on their page. The long and the short description are empty, and the description in the
  JSON-LD block only repeats the name.
- 6 are in no real category of the shop. Their default category is PrestaShop's internal root (`1`) or a hidden
  category without a page that is not in the sitemap (`44`, `257`, `289`). No listing shows them either.

One category (407, Nimi Ayurveda) has no products, and category 465 is empty at the source and has no breadcrumb.

The 4822 product images are 585 MB as an archive. The repository may be 200 MB at most, and Git LFS is not allowed
by the course rules.

## Options considered

**Descriptions.**

- Write a description ourselves (from the name and attributes, or with AI). Pro: all 2182 products stay. Con: the
  text does not come from the source shop, which breaks "data corresponds to the source shop", and a spot check
  against the source would show it.
- Use the name as the description. Pro: no code. Con: a description that says nothing, and it passes validation only
  because validation cannot tell.
- Use the short description when the long one is empty; leave out the product when both are empty (chosen). Pro: only
  text the shop shows. Con: 17 products (0.8%) are missing.

**Products without a category.**

- Put them in a category by their name. Pro: they stay. Con: a guess that has no source.
- Leave them out (chosen). 6 products, 0.3%.

**Empty categories.** Remove them from `categories.json` (chosen), or keep them and fill them with products by hand.
The second one makes the data differ from the source.

**Images.**

- In git or Git LFS. Not possible: the limits above.
- Do not publish them; the init script downloads them again from the source URLs. Pro: nothing to host. Con: 4822
  requests, 1 hour 41 minutes, and the source shop may change.
- One tar.gz in a GitHub Release, 20 samples in git (chosen). The init script can download the archive, and falls back
  to the source URLs when it is not available.

## Decision

The crawl takes the long description, or the short one when the long one is empty. A product that still has no
description, or has no category left after unknown category ids are removed, is not saved. Each one is listed with its
reason in `scraper-results/rejected.json`. Categories without products are removed. Category 465 is skipped on purpose.
Cleaning happens in the crawl, not in the importer, so `products.jsonl` and `categories.json` are always consistent
and `python -m scraper verify` can check them without exceptions.

The archive is made by `python -m scraper archive` and attached to the Release `images-v1`, with its sha256 in the
scraper README. 20 sample images stay in `scraper-results/sample-images/`, chosen with a fixed seed.

## Consequences

- The shop has 2159 products, 160 categories and 4822 images. 23 products of the source shop are missing, and the list
  is in `rejected.json`, so this can be explained at the defence.
- If the source shop adds a description later, a clean crawl picks the product up. Resuming does not refresh saved data.
- The import (D2) and the init script (W3) need no special cases: every product has a description, a category and an image.
- The init script has to download `product-images.tar.gz` from the Release, so the Release must stay available. The
  fallback from the source URLs works for as long as the source shop keeps its images.
