# 0009. Products with variants made from families of source products

- Status: Proposed
- Date: 2026-11-17
- Authors: Jakub Bugnacki

## Context

D3 asks for at least 5 products with at least 2 variants each, every variant with its own stock. W3 compares 10
random products with the source shop (name, price, images), and needs at least 1000 products.

The source shop does not use PrestaShop combinations. Its variants are separate products linked by its own module
`ndx-family`: the product page shows links to the other sizes. The scraper keeps those links in `family`
(`products.jsonl`). 1210 of the 2159 products have one, in 176 families of up to 58 products. Most large families are
not variants of one product but a range (incense sticks in 50 scents, teas of one brand), and the links are often
listed on one side only (851 products list a different set than their family members).

Only 11 families have 2 to 4 products whose names differ in nothing but a quantity (`50ml` and `150ml`, `8g` and
`100g`). These are real variants of one product in one property.

A live change at the defence can be "add a variant to an existing product through the import script or the admin
panel", so adding a variant must be quick and easy to explain.

## Options considered

### How the product with variants relates to the source products

- **One product with combinations replaces the family members (chosen).** The family members are not imported
  separately; their names, prices, images, barcodes and stock move into the combinations. The shop matches the source
  variant by variant: the lecturer who picks a source product finds it in the shop as a variant of the same price,
  with the same images. The shop has a few products fewer than the source (listed below), still far above 1000. The
  product's name is the members' name without the quantity, so it is not exactly the name of any one source product.
- The family members stay, and a new product with combinations is added. Every variant then exists twice: in search
  results, in category lists and in the 10-product comparison, where the new product has no source product at all.
  It would also be 7 products more than the source has.
- Combinations on one of the members, the others kept. The member's name and price then say "50 ml" while "150 ml"
  is chosen, and the other members are still duplicates.
- Make the scraper write combinations. The scraped data would no longer be what the source shop shows, and W2 asks
  for the source data.

### Where the importer learns which products are variants

- **A definitions file, `deploy/importer/variants.json` (chosen).** Each entry gives the product name, the attribute
  group (`Pojemność` or `Waga`) and, for each value, the source product it comes from. Adding a variant is one line
  and a re-run of the import. The choice of families stays visible and reviewable.
- Detect variants from `family` automatically. The links are one-sided and most families are not variants (see
  Context), so a rule would need exceptions, and the result would change whenever the data changes.

### How the combination stores price and weight

- **As differences to the product (chosen).** The product keeps the default variant's net price and weight, and each
  combination stores the difference, which is how PrestaShop stores combinations ("impact"). List pages, which show
  the product's price, show the default variant's price. Both net prices have 6 decimals, so the product's price plus
  the difference gives each variant's source price to the grosz (unit test on the real data).
- Product price 0 and each combination carrying the full price: shows 0 zł wherever the product's own price is used
  without a combination.

## Decision

`deploy/importer/variants.json` lists 7 products (D3 needs 5; one more is a spare, and one has 3 variants). The
importer:

1. checks each entry: at least 2 values, no value or source product twice, every source product in the valid data,
   no source product in two entries, one VAT rate for all of them. An invalid entry is rejected in the report and
   its source products are imported on their own, as without the file;
2. creates the attribute groups and values that are missing, found by name, never changed afterwards;
3. imports the product from the default variant (the first value): its `reference` is that variant's source ID, so
   the next run finds it like any other product, and a product that was imported plain before keeps its ID and URL;
   name and URL slug from the file, the categories and images of all variants;
4. creates, updates or keeps one combination per value, found by its attribute value, with the source product's
   price, weight, `reference` (source ID), EAN, images and stock (`mapping.stock_quantity` of the source ID, as for a
   plain product); a combination whose value left the file is deleted;
5. sets a promotion on each combination whose source product is discounted, and none on the product itself.

A full run deletes the separate copies of the source products that are now variants. Products that are now variants
of another product (8 of the 2159 source products, so the shop has 2151):

| Product with variants | Default variant (product ID kept) | Variants that are no longer products |
|---|---|---|
| Krem odżywczy do twarzy Himalaya (Nourishing Skin Cream) | 7392 (50 ml) | 120 (150 ml) |
| Krem oliwkowy Himalaya Herbals | 5551 (50 ml) | 5723 (150 ml) |
| Pasta do zębów Dant Kanti Patanjali | 4871 (100 g) | 8019 (200 g) |
| Mydło Sandałowe MYSORE SOAP SANDALWOOD | 5212 (75 g) | 5211 (150 g) |
| Kadzidło zapachowe w suszu Bollywood saszetka Song of India | 7736 (8 g) | 8347 (50 g), 8345 (100 g) |
| Żel do mycia twarzy Różany Patanjali | 4869 (60 g) | 8701 (100 g, discounted in the source) |
| Kadzidło w suszu Indian Summer … Song of India | 8355 (100 g) | 8486 (50 g, stock 0) |

Families passed over: Vicco Vajradanti 100/200 ml, because the 200 ml product's source URL names a free face wash
as a gift, so the two may differ in more than the volume; Tea Tree Oil 20/50 ml, because the two are in different
subcategories.

## Consequences

- The shop shows the variant selector on 7 product pages (the ciocia theme draws the values as buttons). Choosing a
  value changes the price, stock, reference and images; a variant with stock 0 cannot be ordered, because the shop
  does not sell products out of stock (`order_out_of_stock` in `shop-settings.php`). Indian Summer 50 g has stock 0.
- The API key needs `combinations`, `product_options` and `product_option_values`
  (`shop/scripts/setup/webservice.php`). A shop installed before this change needs `40-webservice.sh` run again.
- The comparison with the source: a sampled product that is now a variant is found by the product name without the
  quantity, then by choosing the value. Its price, images and barcode match the source product.
- Changing which value comes first makes another source product the default, so the next full run creates a new
  product and deletes the old one (new ID and URL). Adding, renaming or removing other values changes only the
  combinations.
- When a value is added, the product's images change in number, so the importer replaces them all, and the
  existing combinations are updated with the new image IDs.
- Values are created in numeric order ("8 g" before "50 g"), and PrestaShop lists them in the order they were
  created. A value added later to a group goes to the end of its group's list.
- The E2E scenario needs no change: it reads the chosen combination from the product page (`data-product`) and the
  cart line IDs include the combination, and it passes over a product whose default variant has no stock.
