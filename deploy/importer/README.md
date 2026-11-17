# Product importer

Loads the scraped data from `scraper-results/` into the shop through the PrestaShop Webservice API (issue #70,
requirement D2): the category tree, brands, products with prices, VAT, promotions, weight and stock, and the product
images. It also joins a few families of source products into products with variants, from
[`variants.json`](variants.json) (issue #73, D3). A second run finds everything and changes nothing. Design and
reasons: [ADR 0008](../../docs/adr/0008-product-import-through-the-webservice-api.md),
[ADR 0009](../../docs/adr/0009-variants-as-combinations-of-source-families.md) for the variants.

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
| `--variants FILE` | another definitions file instead of `variants.json` (in the image: `/app/variants.json`) |
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
categories                     0          0        160          0          0
products                       0          0       2151          0          0
images                         0          0       4822          0          0
product_options                0          0          2          0          0
product_option_values          0          0          9          0          0
combinations                   0          0         15          0          0
```

- **created**, **updated**, **deleted**: written to the shop in this run.
- **unchanged**: already in the shop with the same values.
- **rejected**: not saved, with the reason in the log as a `REJECTED` line: a line of `products.jsonl` that is not
  valid JSON, a record that breaks `scraper-results/schema.json`, a missing image file, an entry of `variants.json`
  that cannot be used (under `combinations`), or an error message from the shop.

After the import the storefront shows the new data at once: the shop module `ciociamenu` updates the top menu and
clears the page cache whenever the API changes a category, product, price, stock row or image.

The full log is in `deploy/logs/importer.log` (gitignored). The exit code is 0 when nothing was rejected, 1 when
something was, and 2 when the import could not start (no key, shop not reachable, API off, `variants.json` is not
valid JSON).

## How it finds what is already there

| Record | Found by |
|---|---|
| Category | its name and its parent category in the shop |
| Manufacturer | the brand name |
| Product | `reference` = the product's ID in the source shop |
| Stock, promotion | the product, or the combination |
| Images | the number of images the product has in the shop: the same number as in the data means done |
| Attribute group (`Pojemność`), value (`50 ml`) | the name; a value within its group |
| Product with variants | `reference` = the source ID of its default variant (the first value in `variants.json`) |
| Combination | its product and its attribute value |

A product's stock comes from its source ID (`mapping.stock_quantity`), so it is the same on every run. Rules for
prices, weight, barcodes and stock are in `importer/mapping.py`, each with its reason and unit tests.

## Products with variants

The source shop sells each size as a separate product. [`variants.json`](variants.json) names a few such families
and the importer makes one product with a combination per size instead (ADR 0009). An entry:

```json
{
  "name": "Krem oliwkowy Himalaya Herbals",
  "attribute_group": "Pojemność",
  "values": [
    {"value": "50 ml", "source_id": 5551},
    {"value": "150 ml", "source_id": 5723}
  ]
}
```

- `name`: the product's name in the shop (the source names without the quantity).
- `attribute_group`: the property that differs, shown above the buttons on the product page. A new name makes a new
  group.
- `values`: one per variant, with the source product it comes from (its `id` in `products.jsonl`, the number at the
  start of its source URL). The combination takes that product's price, weight, EAN, images and promotion, and its
  ID as `reference`. Its stock is that product's stock, scaled down when the variants together would have more
  than 10, because the product's stock is their sum and no product may have more than 10
  (`mapping.variant_quantities`; Bollywood: 2 + 7 + 9 becomes 1 + 3 + 5). A variant with stock 0 keeps 0.
- The first value is the default variant. Its source product gives the product its description, brand, VAT and its
  `reference`, which is how the next run finds the product again. Put a variant with stock first.

The source products listed here are not imported on their own: a full run deletes their separate copies.

### Adding a variant

1. Find the source product of the new variant in `scraper-results/products.jsonl` (search for its name), and check
   that it is the same product in another size: the same VAT rate, and listed in the default variant's `family`.
2. Add a line to `values` of the product, such as `{"value": "300 ml", "source_id": 1234}`. A source product can be
   in one entry only.
3. Run the import (no `--limit`, so that the separate copy of the new variant is deleted):

   ```sh
   docker compose -f deploy/compose.yaml --profile init run --rm --build importer
   ```

   `--build` puts the edited file into the image. The summary shows `combinations created 1`, and
   `product_option_values created 1` if the value is new in its group. The product page shows the new button.
   The other variants' stock may go down, if the sum would otherwise be above 10.

Replacing a variant's `source_id` with another source product that has the same number of images does not refresh
the images: the importer only compares how many images a product has, so the product keeps the old images and the
combinations keep the old image IDs. Delete the product's images in the admin panel (or the product itself) and run
the import again.

Adding a whole product with variants is the same: a new entry with at least two values. An entry that cannot be used
(a value or source product twice, a source product that is not in the data or already in another entry, different
VAT rates) is reported as `REJECTED combinations` with the reason, and its source products are imported on their own.
Taking a value out of the file deletes its combination; taking out an entry turns its default variant back into a
plain product, and the next full run imports the others on their own again.

The key needs the API resources `combinations`, `product_options` and `product_option_values`. A shop installed before
issue #73 gets them with
`docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/40-webservice.sh` (Git Bash: prefix
`MSYS_NO_PATHCONV=1`); without them the import stops before writing anything, with HTTP 401 and this hint in the log.

## Code

| File | Contents |
|---|---|
| `importer/__main__.py` | options, logging, and `run()`, which calls the steps in order |
| `importer/steps.py` | one function per step: read the shop, categories, brands, products with stock and promotion, then their images, the products with variants and their combinations, delete what is not in the data |
| `importer/variants.py` | reads and checks `variants.json`, and makes the product record of a product with variants |
| `importer/mapping.py` | pure conversion rules: net price, weight, stock, barcodes, slugs, visible text, combination price and weight |
| `importer/api.py` | the only code that talks to the shop: JSON for reading, XML for writing |
| `importer/data.py` | reads the scraped files and validates them against the schema |
| `importer/report.py` | the counts and the `REJECTED` log lines |
| `importer/config.py` | settings from the environment |

## Tests

They need no shop, only the files in `scraper-results/`. The tests of the variant steps (`tests/test_variants.py`)
run against `tests/fake_shop.py`, an in-memory stand-in for the API that also copies what PrestaShop does on its own
(stock rows for new combinations, the product's stock as their sum). From `deploy/importer/`, with Python 3.12 and the
dependencies (`pip install -r requirements.txt pytest`):

```sh
python -m pytest
```

CI runs them in the `scraper` job, and `ruff check .` from the repository root covers this code too.
