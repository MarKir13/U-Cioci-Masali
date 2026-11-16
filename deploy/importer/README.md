# Product importer

Loads the scraped data from `scraper-results/` into the shop through the PrestaShop Webservice API (issue #70,
requirement D2): the category tree, brands, products with prices, VAT, promotions, weight and stock, and the product
images. A second run finds everything and changes nothing. Design and reasons:
[ADR 0008](../../docs/adr/0008-product-import-through-the-webservice-api.md).

## Running it

The shop must be running, and the images unpacked into `scraper-results/images/` (see the scraper README). Only the
images of the selected products are needed: with `--categories 85,99`, the files of other products may be missing.
From the repository root:

```sh
docker compose -f deploy/compose.yaml --profile init run --rm --build importer
```

`--profile init` is needed because the `importer` service is not started by `up`. Compose waits until the shop is
healthy, builds the image the first time, runs one import and removes the container. The importer uses the API key
`PS_WEBSERVICE_KEY` and the shop's domain `localhost:<HTTPS_PORT>` from `deploy/.env`.

| Option | Meaning |
|---|---|
| `--limit N` | only the first N products of `products.jsonl` (all categories are still imported) |
| `--categories 8,193` | only products in these source categories or their subcategories |
| `--dry-run` | read the data and the shop and count what would change, write nothing |
| `--workers N` | products handled at the same time (default 8; fewer on a slow machine) |
| `--verbose` | DEBUG messages on the console too |

Options go after `importer`, for example `... run --rm importer --limit 20`. Only a full run (no `--limit` and no
`--categories`) deletes products, categories and manufacturers that are not in the data, such as the installer's
demo catalogue; a subset run never deletes anything. A rejected record still counts as in the data: its copy from
an earlier run stays in the shop, and if a category or manufacturer was rejected, no category or manufacturer is
deleted in that run. If a line of `products.jsonl` cannot be read, no product is deleted either, since that line's
product is unknown. Specific prices made by a catalogue price rule are never touched.

## What it prints

A summary per resource, for example after a second run:

```
                   created    updated  unchanged    deleted   rejected
categories               0          0        160          0          0
products                 0          0       2159          0          0
images                   0          0       4822          0          0
```

- **created**, **updated**, **deleted**: written to the shop in this run.
- **unchanged**: already in the shop with the same values.
- **rejected**: not saved, with the reason in the log as a `REJECTED` line: a line of `products.jsonl` that is not
  valid JSON, a record that breaks `scraper-results/schema.json`, a missing image file, or an error message from the
  shop.

After the import the storefront shows the new data at once: the shop module `ciociamenu` updates the top menu and
clears the page cache whenever the API changes a category, product, price, stock row or image.

The full log is in `deploy/logs/importer.log` (gitignored). The exit code is 0 when nothing was rejected, 1 when
something was, and 2 when the import could not start (no key, shop not reachable, API off).

## How it finds what is already there

| Record | Found by |
|---|---|
| Category | its name and its parent category in the shop |
| Manufacturer | the brand name |
| Product | `reference` = the product's ID in the source shop |
| Stock, promotion | the product |
| Images | the number of images the product has in the shop: the same number as in the data means done |

A product's stock comes from its source ID (`mapping.stock_quantity`), so it is the same on every run. Rules for
prices, weight, barcodes and stock are in `importer/mapping.py`, each with its reason and unit tests.

## Code

| File | Contents |
|---|---|
| `importer/__main__.py` | options, logging, and `run()`, which calls the steps in order |
| `importer/steps.py` | one function per step: read the shop, categories, brands, products with stock and promotion, then their images, delete what is not in the data |
| `importer/mapping.py` | pure conversion rules: net price, weight, stock, barcodes, slugs, visible text |
| `importer/api.py` | the only code that talks to the shop: JSON for reading, XML for writing |
| `importer/data.py` | reads the scraped files and validates them against the schema |
| `importer/report.py` | the counts and the `REJECTED` log lines |
| `importer/config.py` | settings from the environment |

## Tests

They need no shop, only the files in `scraper-results/`. From `deploy/importer/`, with Python 3.12 and the
dependencies (`pip install -r requirements.txt pytest`):

```sh
python -m pytest
```

CI runs them in the `scraper` job, and `ruff check .` from the repository root covers this code too.
