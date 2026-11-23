"""The import steps. __main__.run() calls them in order; each step does only its own job.

Every step compares what the data says with what the shop already has (read once by read_shop), and
creates, updates or leaves each record alone. That is what makes a second run safe: it finds everything
and changes nothing. The keys used to find existing records are explained in ADR 0008:
- category: its name and its parent in the shop (its description and position are updated too);
- manufacturer: its name;
- product: `reference` = the product ID in the source shop (for a product with variants: of its default variant);
- attribute group and value: the name (a value within its group);
- combination: its product and its attribute value.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from . import mapping, variants
from .api import ApiError, Lang, ShopApi, text
from .report import Report
from .variants import VariantProduct

log = logging.getLogger("importer")

# PrestaShop's "use the shop setting" for out-of-stock orders; the shop setting denies them (PS_ORDER_OUT_OF_STOCK = 0)
OUT_OF_STOCK_DEFAULT = 2
NO_DATE = "0000-00-00 00:00:00"

# Saving a product also updates PrestaShop's search index, and two saves at the same moment deadlock in MySQL
# (HTTP 500, product half saved). So products are saved one at a time; their images, the slow part, are not.
PRODUCT_SAVE = threading.Lock()


@dataclass
class Shop:
    """What the shop holds before the import, read once so that the steps compare with memory."""

    home_id: int
    tax_groups: dict[float, int]  # VAT rate -> tax rule group
    categories: dict[tuple[int, str], dict]  # (parent ID, name) -> category
    manufacturers: dict[str, dict]  # name -> manufacturer
    products: dict[str, dict]  # reference -> product, with its associations (categories, images, stock)
    all_products: list[dict]  # every product, also those without a reference (the delete step needs them all)
    stock: dict[tuple[int, int], dict]  # (product ID, combination ID or 0) -> its stock row
    specific_prices: dict[tuple[int, int], list[dict]]  # (product ID, combination ID or 0) -> its specific prices
    # (product ID, combination ID or 0) -> the end date of its promotion, kept apart from the specific price (#111)
    promo_ends: dict[tuple[int, int], dict] = field(default_factory=dict)
    # Products with variants (variants.json, ADR 0009)
    combinations: dict[int, list[dict]] = field(default_factory=dict)  # product ID -> its combinations
    option_groups: dict[str, dict] = field(default_factory=dict)  # name -> attribute group
    option_values: dict[tuple[int, str], dict] = field(default_factory=dict)  # (group ID, name) -> attribute value


# --- Step 0: what is already in the shop -------------------------------------------------------------


def read_shop(api: ShopApi) -> Shop:
    roots = api.list("categories", display="[id]", filters={"is_root_category": 1})
    categories = api.list(
        "categories", display="[id,id_parent,name,link_rewrite,active,level_depth,description,position]"
    )
    products = api.list("products", display="full")
    # The rows of products (combination 0) and of their combinations
    stock_rows = api.list("stock_availables", display="full")
    specific_prices: dict[tuple[int, int], list[dict]] = {}
    # Only prices not made by a catalogue price rule: set_promotion deletes the ones it does not want, and
    # prices from a rule belong to that rule (the shop recreates them from it)
    for price in api.list("specific_prices", display="full", filters={"id_specific_price_rule": 0}):
        specific_prices.setdefault(_product_and_combination(price), []).append(price)
    combinations: dict[int, list[dict]] = {}
    for combination in api.list("combinations", display="full"):
        combinations.setdefault(int(combination["id_product"]), []).append(combination)
    option_groups = api.list("product_options", display="[id,name]")
    promo_ends = read_promo_ends(api)
    option_values = api.list("product_option_values", display="[id,id_attribute_group,name]")

    return Shop(
        home_id=int(roots[0]["id"]),
        tax_groups=read_tax_groups(api),
        categories={(int(c["id_parent"]), text(c["name"])): c for c in categories},
        manufacturers={text(m["name"]): m for m in api.list("manufacturers", display="[id,name,active]")},
        products={str(p.get("reference", "")): p for p in products},
        all_products=products,
        stock={_product_and_combination(s): s for s in stock_rows},
        specific_prices=specific_prices,
        promo_ends={_product_and_combination(e): e for e in promo_ends},
        combinations=combinations,
        option_groups={text(g["name"]): g for g in option_groups},
        option_values={(int(v["id_attribute_group"]), text(v["name"])): v for v in option_values},
    )


def read_promo_ends(api: ShopApi) -> list[dict]:
    """The promotion end dates (#111). The resource comes from our module ciociaomnibus, so a shop set up before
    it existed has no such resource, table or permission until the setup scripts run again."""
    try:
        return api.list("ciocia_promo_ends", display="full")
    except ApiError as error:
        raise ApiError(
            error.status,
            f"{error.message} (resource ciocia_promo_ends of module ciociaomnibus: on a shop set up before #111, "
            "run shop/scripts/post-install/30-configure-shop.sh and then 40-webservice.sh, see AGENTS.md)",
        ) from error


def _product_and_combination(record: dict) -> tuple[int, int]:
    """(product ID, combination ID) of a stock row or specific price; 0 for the product itself."""
    return int(record["id_product"]), int(record.get("id_product_attribute") or 0)


def read_tax_groups(api: ShopApi) -> dict[float, int]:
    """VAT rate -> the tax rule group whose only rate it is.

    Found through the API, not by fixed IDs. Only groups with a single rate count: "EU VAT For Virtual
    Products" also contains 23%, but it is not the group for Polish goods ("PL Standard Rate (23%)").
    """
    rate_of_tax = {int(t["id"]): float(t["rate"]) for t in api.list("taxes", display="[id,rate]")}
    rates_of_group: dict[int, set[float]] = {}
    for rule in api.list("tax_rules", display="[id_tax_rules_group,id_tax]"):
        group = int(rule["id_tax_rules_group"])
        rates_of_group.setdefault(group, set()).add(rate_of_tax.get(int(rule["id_tax"]), -1.0))
    active = {int(g["id"]) for g in api.list("tax_rule_groups", display="[id,active,deleted]") if _flag(g, "active")}

    groups: dict[float, int] = {}
    for group, rates in sorted(rates_of_group.items()):
        if group in active and len(rates) == 1:
            groups.setdefault(rates.pop(), group)
    return groups


def _flag(record: dict, field: str) -> bool:
    return str(record.get(field, "0")) == "1"


# --- Step 1: categories ------------------------------------------------------------------------------


def import_categories(api: ShopApi, shop: Shop, categories: list[dict], report: Report) -> dict[int, int]:
    """Creates or updates the category tree, parents first. Returns source category ID -> shop category ID."""
    shop_ids: dict[int, int] = {}
    for category in mapping.parents_first(categories):
        source_parent = category["parent_id"]
        parent = shop.home_id if source_parent is None else shop_ids.get(source_parent)
        if parent is None:
            report.reject("categories", category["id"], f"its parent {source_parent} was not imported")
            continue
        fields = {
            "id_parent": parent,
            "active": 1,
            "name": Lang(category["name"]),
            "link_rewrite": Lang(mapping.link_rewrite(category["url"], category["name"])),
            # The text under the category name, as on the source (the theme shows it on the first page)
            "description": Lang(mapping.without_source_links(category.get("description") or "")),
        }
        if category.get("position") is not None:
            # Order among its siblings, as on the source. The data counts from 1, PrestaShop from 0.
            fields["position"] = category["position"] - 1
        existing = shop.categories.get((parent, category["name"]))
        try:
            record = save_record("categories", api, existing, fields, report)
            if existing is None and differs(record, fields):
                # PrestaShop puts a new category last among its siblings whatever position it is sent
                # (Category::add), so the position is set by an update. An update stores it as sent.
                api.update("categories", int(record["id"]), fields)
            shop_ids[category["id"]] = int(record["id"])
        except ApiError as error:
            report.reject("categories", category["id"], error.message)
    return shop_ids


# --- Step 2: brands as manufacturers ----------------------------------------------------------------


def import_manufacturers(api: ShopApi, shop: Shop, products: list[dict], report: Report) -> dict[str, int]:
    """One manufacturer per brand name. Returns brand -> manufacturer ID."""
    shop_ids: dict[str, int] = {}
    for brand in sorted({p["brand"] for p in products if p.get("brand")}):
        fields = {"name": brand, "active": 1}
        try:
            shop_ids[brand] = save("manufacturers", api, shop.manufacturers.get(brand), fields, report)
        except ApiError as error:
            report.reject("manufacturers", brand, error.message)
    return shop_ids


# --- Steps 3-6: products, each with its stock, promotion and images ----------------------------------


def import_products(
    api: ShopApi,
    shop: Shop,
    products: list[dict],
    category_ids: dict[int, int],
    brand_ids: dict[str, int],
    data_dir: Path,
    workers: int,
    report: Report,
) -> None:
    """Each product with its stock, promotion and images, `workers` products at the same time.

    Only the product save waits for PRODUCT_SAVE. Image uploads are the slow part (PrestaShop makes 5 thumbnails
    of each image) and run side by side. Saving all products first and uploading all images afterwards was
    measured too and was slower (ADR 0008).
    """

    def one(product: dict) -> None:
        product_id = import_product(api, shop, product, category_ids, brand_ids, report)
        if product_id is not None:
            existing = shop.products.get(str(product["id"])) or {}
            set_images(api, existing, product, product_id, data_dir, report)

    in_parallel("products", products, one, workers, report)


def in_parallel(name: str, products: list[dict], work, workers: int, report: Report) -> None:
    """Runs `work(product)` for every product, `workers` at a time, and logs the progress."""
    started = time.monotonic()
    done = 0

    def one(product: dict) -> None:
        try:
            work(product)
        except Exception as error:  # noqa: BLE001 - one broken product must not stop the other 2000
            report.reject("products", product["id"], f"unexpected error: {error!r}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(one, products):
            done += 1
            if done % 200 == 0 or done == len(products):
                log.info("%s: %d/%d (%.0f s)", name, done, len(products), time.monotonic() - started)


def import_product(
    api: ShopApi,
    shop: Shop,
    product: dict,
    category_ids: dict[int, int],
    brand_ids: dict[str, int],
    report: Report,
) -> int | None:
    """Saves one product with its stock and promotion. Returns its shop ID, or None if it was rejected."""
    fields = product_fields(product, shop, category_ids, brand_ids)
    if isinstance(fields, str):
        report.reject("products", product["id"], fields)
        return None
    existing = shop.products.get(str(product["id"]))
    try:
        waiting = time.monotonic()
        with PRODUCT_SAVE:
            # Large next to "PUT/POST products": the one-at-a-time saves hold the other workers back
            api.timings.add("wait for product save", time.monotonic() - waiting)
            saved = save_record("products", api, existing, fields, report)
    except ApiError as error:
        report.reject("products", product["id"], error.message)
        return None
    product_id = int(saved["id"])
    # A product that had variants in an earlier run (its entry was taken out of variants.json) loses them.
    # Before the stock, because deleting a combination changes the product's stock.
    had_variants = remove_combinations(api, shop.combinations.get(product_id, []), product["id"], report)
    set_stock(
        api,
        product_stock_row(shop, saved),
        product_id,
        0,
        mapping.stock_quantity(product["id"]),
        product["id"],
        report,
        force=had_variants,
    )
    set_promotion(api, shop, product, product_id, 0, report)
    return product_id


def product_fields(product: dict, shop: Shop, category_ids: dict[int, int], brand_ids: dict[str, int]) -> dict | str:
    """Everything the importer sets on a product, or the reason it cannot be imported.

    An update through the API replaces the whole product (left-out fields are emptied), so updates send
    this complete set as well.
    """
    categories = [category_ids[c] for c in product["category_ids"] if c in category_ids]
    if not categories:
        return "none of its categories was imported"
    tax_group = shop.tax_groups.get(product["vat_rate"])
    if tax_group is None:
        return f"no tax rule group for VAT {product['vat_rate']}%"
    ean13, upc = mapping.barcodes(product.get("ean"))
    description, description_short = mapping.descriptions(product)
    return {
        "reference": product["id"],
        "id_manufacturer": brand_ids.get(product.get("brand") or "", 0),
        # The first category is the product's default one in the source (ADR 0004)
        "id_category_default": categories[0],
        "id_tax_rules_group": tax_group,
        "price": mapping.net_price(product["regular_price"], product["vat_rate"]),
        "weight": mapping.weight_kg(product.get("weight")),
        "ean13": ean13,
        "upc": upc,
        "active": 1,
        "state": 1,
        "available_for_order": 1,
        "show_price": 1,
        "visibility": "both",
        "condition": "new",
        "minimal_quantity": 1,
        "name": Lang(product["name"]),
        "description": Lang(description),
        "description_short": Lang(description_short),
        # A product with variants has a slug made from its own name (variants.product_record)
        "link_rewrite": Lang(product.get("link_rewrite") or mapping.link_rewrite(product["url"], product["name"])),
        "associations": {"categories": [("category", {"id": c}) for c in categories]},
    }


def product_stock_row(shop: Shop, saved: dict) -> dict | None:
    """The stock row of a product itself (combination 0). PrestaShop makes it together with the product, so for
    a product created just now, which is not in the snapshot, it comes from the create response."""
    product_id = int(saved["id"])
    row = shop.stock.get((product_id, 0))
    if row is None:
        rows = saved.get("associations", {}).get("stock_availables", [])
        found = next((r for r in rows if str(r.get("id_product_attribute", "0")) == "0"), None)
        # The create response lists only the row's ID, so the quantity is unknown: it gets written
        row = {"id_shop": saved.get("id_shop_default", 1), **found, "quantity": None, "new": True} if found else None
    return row


def set_stock(
    api: ShopApi,
    row: dict | None,
    product_id: int,
    combination_id: int,
    quantity: int,
    key: object,
    report: Report,
    force: bool = False,
) -> None:
    """Sets the stock row of a product (combination_id 0) or of one of its combinations to `quantity`.

    PrestaShop makes the rows itself, with the product and with each combination, so the import only updates
    them. `force` writes the row even if it looks right, because the shop has just changed it.
    """
    if row is None and (product_id < 0 or combination_id < 0):
        # --dry-run: the product or combination was not really created, so there is no row
        report.count("stock", "created")
        return
    if row is None:
        what = "combination" if combination_id else "product"
        report.reject("stock", key, f"PrestaShop created no stock row for the {what}")
        return
    created = bool(row.get("new"))
    same = row.get("quantity") is not None and int(row["quantity"]) == quantity
    if same and not force and not created and int(row["out_of_stock"]) == OUT_OF_STOCK_DEFAULT:
        report.count("stock", "unchanged")
        return
    fields = {
        "id_product": product_id,
        "id_product_attribute": combination_id,
        "id_shop": row.get("id_shop", 1),
        "id_shop_group": row.get("id_shop_group", 0),
        "quantity": quantity,
        "depends_on_stock": 0,
        "out_of_stock": OUT_OF_STOCK_DEFAULT,
        "location": "",
    }
    try:
        api.update("stock_availables", int(row["id"]), fields)
        report.count("stock", "created" if created else "updated")
    except ApiError as error:
        report.reject("stock", key, error.message)


def promotion_fields(product: dict, product_id: int, combination_id: int = 0) -> dict:
    """A specific price that takes the regular gross price down to the promotional one, for everybody, always.

    The reduction is an amount with tax included, so the shop shows exactly the source's promotional price.
    With a combination ID it applies to that combination only (a variant whose source product is discounted).
    """
    return {
        "id_product": product_id,
        "id_product_attribute": combination_id,
        "id_shop": 0,
        "id_shop_group": 0,
        "id_cart": 0,
        "id_currency": 0,
        "id_country": 0,
        "id_group": 0,
        "id_customer": 0,
        "id_specific_price_rule": 0,
        "price": -1,  # keep the product's own price, only take the reduction off
        "from_quantity": 1,
        "reduction": mapping.promotion_amount(product["regular_price"], product["price"]),
        "reduction_tax": 1,
        "reduction_type": "amount",
        "from": NO_DATE,
        "to": NO_DATE,
    }


def set_promotion(
    api: ShopApi, shop: Shop, product: dict, product_id: int, combination_id: int, report: Report
) -> None:
    """One specific price per discounted product (or combination); none for the others. The same for its end date."""
    set_promo_end(api, shop.promo_ends.get((product_id, combination_id)), product, product_id, combination_id, report)
    existing = shop.specific_prices.get((product_id, combination_id), [])
    try:
        if not product["has_discount"]:
            for price in existing:
                api.delete("specific_prices", int(price["id"]))
                report.count("specific_prices", "deleted")
            return
        fields = promotion_fields(product, product_id, combination_id)
        first, extra = (existing[0], existing[1:]) if existing else (None, [])
        save("specific_prices", api, first, fields, report)
        for price in extra:
            api.delete("specific_prices", int(price["id"]))
            report.count("specific_prices", "deleted")
    except ApiError as error:
        report.reject("specific_prices", product["id"], error.message)


def set_promo_end(
    api: ShopApi, existing: dict | None, product: dict, product_id: int, combination_id: int, report: Report
) -> None:
    """The end date of the source's promotion, shown on product cards: "Cena przed: 26,50 zł · do 14.11.2026" (#111).

    It goes to our module's table (ciociaomnibus, resource ciocia_promo_ends), not to "to" of the specific price:
    the source's promotions end within days, and PrestaShop would stop applying ours on that date (D3 needs 20+).
    A product without a discount or without an end date has no row.
    """
    end = mapping.promo_end_date(product.get("promo_end")) if product["has_discount"] else None
    try:
        if end is None:
            if existing is not None:
                api.delete("ciocia_promo_ends", int(existing["id"]))
                report.count("ciocia_promo_ends", "deleted")
            return
        fields = {"id_product": product_id, "id_product_attribute": combination_id, "date_end": end}
        save("ciocia_promo_ends", api, existing, fields, report)
    except ApiError as error:
        report.reject("ciocia_promo_ends", product["id"], error.message)


def set_images(api: ShopApi, existing: dict, product: dict, product_id: int, data_dir: Path, report: Report) -> bool:
    """Uploads the product's images in the listed order; the first one becomes the cover.

    The shop itself says what is already there: a product with as many images as the data lists is left
    alone. Otherwise its images are replaced, so the order and the cover are right. Returns True if it
    changed the images.
    """
    current = [int(i["id"]) for i in existing.get("associations", {}).get("images", [])]
    wanted = product["images"]
    if len(current) == len(wanted):
        report.count("images", "unchanged", len(wanted))
        return False
    for image_id in current:
        try:
            api.delete_image(product_id, image_id)
            report.count("images", "deleted")
        except ApiError as error:
            report.reject("images", f"{product['id']}/{image_id}", error.message)
    for image in wanted:
        try:
            api.upload_image(product_id, data_dir / image["local_path"])
            report.count("images", "created")
        except ApiError as error:
            report.reject("images", image["local_path"], error.message)
    return True


# --- Steps 3-6 for products with variants (variants.json, ADR 0009) ---------------------------------


# How the shop shows an attribute group on the product page: "radio" gives one button per value, which the
# ciocia theme draws as pills (custom.css, "Variant selector")
GROUP_TYPE = "radio"


def import_variant_products(
    api: ShopApi,
    shop: Shop,
    products: list[VariantProduct],
    category_ids: dict[int, int],
    brand_ids: dict[str, int],
    data_dir: Path,
    report: Report,
) -> None:
    """The attribute groups and values, then each product with its combinations, one product at a time.

    After import_products() has finished, so no other product is saved at the same moment (PRODUCT_SAVE).
    """
    if not products:
        return
    value_ids = import_attributes(api, shop, products, report)
    for product in products:
        try:
            import_variant_product(api, shop, product, value_ids, category_ids, brand_ids, data_dir, report)
        except Exception as error:  # noqa: BLE001 - as in in_parallel: one broken product must not stop the others
            report.reject("products", product.name, f"unexpected error: {error!r}")


def import_attributes(
    api: ShopApi, shop: Shop, products: list[VariantProduct], report: Report
) -> dict[tuple[str, str], int]:
    """Creates the attribute groups and values that are missing. Returns (group, value) -> value ID.

    Found by name and never changed afterwards. New values are created smallest number first
    (variants.values_by_group), and the shop lists values in the order they were created, so "8 g" comes
    before "50 g" on the product page. A value added later goes to the end of its group.
    """
    value_ids: dict[tuple[str, str], int] = {}
    for group, values in variants.values_by_group(products).items():
        fields = {"is_color_group": 0, "group_type": GROUP_TYPE, "name": Lang(group), "public_name": Lang(group)}
        try:
            group_id = _find_or_create("product_options", api, shop.option_groups.get(group), fields, report)
        except ApiError as error:
            report.reject("product_options", group, error.message)
            continue
        for value in values:
            fields = {"id_attribute_group": group_id, "name": Lang(value)}
            existing = shop.option_values.get((group_id, value))
            try:
                value_ids[(group, value)] = _find_or_create("product_option_values", api, existing, fields, report)
            except ApiError as error:
                report.reject("product_option_values", f"{group}: {value}", error.message)
    return value_ids


def _find_or_create(resource: str, api: ShopApi, existing: dict | None, fields: dict, report: Report) -> int:
    if existing is not None:
        report.count(resource, "unchanged")
        return int(existing["id"])
    created = api.create(resource, fields)
    report.count(resource, "created")
    return int(created["id"])


def import_variant_product(
    api: ShopApi,
    shop: Shop,
    product: VariantProduct,
    value_ids: dict[tuple[str, str], int],
    category_ids: dict[int, int],
    brand_ids: dict[str, int],
    data_dir: Path,
    report: Report,
) -> None:
    """One product with a combination per variant, in this order:

    1. the product, made from the default variant's source product (variants.product_record);
    2. its images: those of all variants, the default variant's first;
    3. the combinations: each with its source product's price, weight, reference, barcode and images;
    4. the stock of each combination, and the product's own stock row as their sum (how PrestaShop shows it),
       at most 10 (mapping.variant_quantities);
    5. a promotion on each combination whose source product is discounted, and none on the product itself.
    """
    record = variants.product_record(product)
    key = f"{product.name} (source {record['id']})"
    fields = product_fields(record, shop, category_ids, brand_ids)
    if isinstance(fields, str):
        report.reject("products", key, fields)
        return
    existing = shop.products.get(str(record["id"]))
    before = shop.combinations.get(int(existing["id"]), []) if existing else []
    default_value = value_ids.get((product.group, product.variants[0].value))
    default_before = next((c for c in before if _value_ids(c) == [default_value]), None)
    if default_before is not None and existing is not None and "id_default_combination" in existing:
        # An update through the API empties what it leaves out, so it would lose the default combination
        fields["id_default_combination"] = int(default_before["id"])
    try:
        saved = save_record("products", api, existing, fields, report)
    except ApiError as error:
        report.reject("products", key, error.message)
        return
    product_id = int(saved["id"])
    # The product's own promotion from before it had variants: now each variant has its own
    set_promotion(api, shop, record, product_id, 0, report)

    changed = set_images(api, existing or {}, record, product_id, data_dir, report)
    images = variant_image_ids(api, existing or {}, product, product_id, changed)

    combinations = set_combinations(api, product, product_id, before, value_ids, images, key, report)
    if not combinations:
        return

    # Stock: each combination's row, then the product's row with the sum
    if any(new for _, _, new in combinations) and product_id > 0 and not api.dry_run:
        rows = api.list("stock_availables", display="full", filters={"id_product": product_id})
        stock = {_product_and_combination(r): r for r in rows}
    else:
        stock = shop.stock
    # The stock of all variants, so that their sum stays within 0-10 (mapping.variant_quantities)
    source_ids = [v.product["id"] for v in product.variants]
    quantities = dict(zip(source_ids, mapping.variant_quantities(source_ids), strict=True))
    total = 0
    for variant, combination_id, new in combinations:
        quantity = quantities[variant.product["id"]]
        total += quantity
        row = stock.get((product_id, combination_id))
        if new and row is not None:
            row = {**row, "new": True}  # made by the shop just now, with quantity 0: counted as created
        set_stock(api, row, product_id, combination_id, quantity, f"{key} {variant.value}", report)
    product_row = stock.get((product_id, 0)) or product_stock_row(shop, saved)
    if existing is None and product_row is not None:
        product_row = {**product_row, "new": True}
    set_stock(api, product_row, product_id, 0, total, key, report)

    for variant, combination_id, _ in combinations:
        set_promotion(api, shop, variant.product, product_id, combination_id, report)


def variant_image_ids(
    api: ShopApi, existing: dict, product: VariantProduct, product_id: int, changed: bool
) -> list[list[int]]:
    """The shop's image IDs of each variant, in the order of product.variants.

    The images were uploaded in the order of variants.product_record() (variant by variant), and the shop
    keeps them in that order, so the first images belong to the first variant, and so on. If the shop has
    another number of images (an upload was rejected), no combination gets images rather than wrong ones.
    """
    if product_id < 0:
        return [[] for _ in product.variants]
    source = api.get("products", product_id) if changed and not api.dry_run else existing
    ids = [int(i["id"]) for i in source.get("associations", {}).get("images", [])]
    counts = [len(v.product["images"]) for v in product.variants]
    if len(ids) != sum(counts):
        expected = sum(counts)
        log.warning("product %d has %d images, expected %d: its combinations get none", product_id, len(ids), expected)
        return [[] for _ in product.variants]
    result, start = [], 0
    for count in counts:
        result.append(ids[start : start + count])
        start += count
    return result


def combination_fields(
    product: VariantProduct, index: int, product_id: int, value_id: int, image_ids: list[int]
) -> dict:
    """Everything the importer sets on the combination of product.variants[index].

    Price and weight are differences to the product's (the default variant's), as PrestaShop stores them.
    """
    variant = product.variants[index]
    source, default = variant.product, product.default
    ean13, upc = mapping.barcodes(source.get("ean"))
    return {
        "id_product": product_id,
        "reference": source["id"],
        "ean13": ean13,
        "upc": upc,
        "price": mapping.price_impact(source["regular_price"], default["regular_price"], default["vat_rate"]),
        "weight": mapping.weight_impact(source.get("weight"), default.get("weight")),
        "minimal_quantity": 1,
        "default_on": 1 if index == 0 else 0,
        "associations": {
            "product_option_values": [("product_option_value", {"id": value_id})],
            "images": [("image", {"id": i}) for i in image_ids],
        },
    }


def set_combinations(
    api: ShopApi,
    product: VariantProduct,
    product_id: int,
    before: list[dict],
    value_ids: dict[tuple[str, str], int],
    images: list[list[int]],
    key: str,
    report: Report,
) -> list[tuple[variants.Variant, int, bool]]:
    """Creates, updates or keeps a combination per variant, and deletes the product's other combinations.

    A combination is found by its attribute value. The others go first, because a product can have only
    one default combination and a new default one must not meet the old one. Returns (variant, combination
    ID, created now) for every combination that is in the shop after this.
    """
    by_value: dict[int, dict] = {}
    wanted = {value_ids.get((product.group, v.value)) for v in product.variants}
    for combination in before:
        values = _value_ids(combination)
        if len(values) == 1 and values[0] in wanted and values[0] not in by_value:
            by_value[values[0]] = combination
        else:
            _delete(api, "combinations", int(combination["id"]), f"{key} combination {combination['id']}", report)

    result = []
    for index, variant in enumerate(product.variants):
        value_id = value_ids.get((product.group, variant.value))
        if value_id is None:
            report.reject("combinations", f"{key} {variant.value}", "its attribute value was not imported")
            continue
        fields = combination_fields(product, index, product_id, value_id, images[index])
        existing = by_value.get(value_id)
        try:
            saved = save_record("combinations", api, existing, fields, report)
        except ApiError as error:
            report.reject("combinations", f"{key} {variant.value}", error.message)
            continue
        result.append((variant, int(saved["id"]), existing is None))
    return result


def remove_combinations(api: ShopApi, combinations: list[dict], key: object, report: Report) -> bool:
    """Deletes a product's combinations, for a product that is no longer in variants.json. True if it had any."""
    for combination in combinations:
        _delete(api, "combinations", int(combination["id"]), f"{key} combination {combination['id']}", report)
    return bool(combinations)


def _value_ids(combination: dict) -> list[int]:
    return [int(v["id"]) for v in combination.get("associations", {}).get("product_option_values", [])]


# --- Step 7: remove what does not come from the data (the installer's demo catalogue) -----------------


def remove_other_records(
    api: ShopApi,
    shop: Shop,
    products: list[dict],
    rejected_product_ids: set[int],
    category_ids: dict[int, int],
    brand_ids: dict[str, int],
    report: Report,
    all_lines_read: bool = True,
) -> None:
    """Deletes products, categories and manufacturers that are not in the data, such as the demo ones.

    Only after a full run: with --limit or --categories, everything outside the subset would be deleted.

    A rejected record is still in the data, so its copy from an earlier run stays in the shop. Otherwise a run
    with the image archive half unpacked would delete every product whose image file is missing. Products are
    kept by their source ID. A rejected category or manufacturer cannot be matched to its copy in the shop, so
    when any was rejected, that whole kind is left alone in this run; manufacturers also when a product was
    rejected, because its brand is unknown. An unreadable line of products.jsonl (all_lines_read False) has no
    product ID at all, so then no product and no manufacturer is deleted.
    """
    if not all_lines_read:
        log.warning("products.jsonl has unreadable lines, so no product is deleted")
    else:
        references = {str(p["id"]) for p in products} | {str(i) for i in rejected_product_ids}
        for product in shop.all_products:
            reference = str(product.get("reference", ""))
            if reference not in references:
                _delete(api, "products", int(product["id"]), reference or text(product.get("name")), report)

    if report.rejected_of("categories"):
        log.warning("categories rejected in this run, so no category is deleted")
    else:
        keep = set(category_ids.values()) | {shop.home_id}
        others = [c for c in shop.categories.values() if int(c["id"]) not in keep and int(c["level_depth"]) > 1]
        # Children before parents: deleting a parent would already delete its children
        for category in sorted(others, key=lambda c: -int(c["level_depth"])):
            _delete(api, "categories", int(category["id"]), text(category["name"]), report)

    if report.rejected_of("manufacturers") or rejected_product_ids or not all_lines_read:
        log.warning("manufacturers or products rejected in this run, so no manufacturer is deleted")
    else:
        for name, manufacturer in shop.manufacturers.items():
            if name not in brand_ids:
                _delete(api, "manufacturers", int(manufacturer["id"]), name, report)


def _delete(api: ShopApi, resource: str, record_id: int, key: object, report: Report) -> None:
    try:
        api.delete(resource, record_id)
        report.count(resource, "deleted")
        log.info("deleted %s %s (ID %d), not in the data", resource, key, record_id)
    except ApiError as error:
        if error.status == 404:  # already gone with its parent
            return
        report.reject(resource, key, error.message)


# --- Shared: create, update or leave alone -----------------------------------------------------------


def save(resource: str, api: ShopApi, existing: dict | None, fields: dict, report: Report) -> int:
    """Creates the record, updates it if it differs from `fields`, or leaves it. Returns its shop ID."""
    return int(save_record(resource, api, existing, fields, report)["id"])


def save_record(resource: str, api: ShopApi, existing: dict | None, fields: dict, report: Report) -> dict:
    """Like save(), but returns the record: the shop's answer for a new one, else the one read before."""
    if existing is None:
        created = api.create(resource, fields)
        report.count(resource, "created")
        return created
    if differs(existing, fields):
        api.update(resource, int(existing["id"]), fields)
        report.count(resource, "updated")
    else:
        report.count(resource, "unchanged")
    return existing


def differs(existing: dict, fields: dict) -> bool:
    """True if any field the importer sets has another value in the shop."""
    for name, wanted in fields.items():
        if name == "associations":
            for group, items in wanted.items():
                have = {str(i["id"]) for i in existing.get("associations", {}).get(group, [])}
                if have != {str(item["id"]) for _, item in items}:
                    return True
            continue
        have = existing.get(name)
        if name in ("description", "description_short"):
            if mapping.visible_text(text(have)) != mapping.visible_text(str(wanted)):
                return True
            # A removed video player leaves the visible text as it was, so a shop imported before the
            # importer removed them would otherwise keep the players for good (mapping.without_videos)
            if mapping.VIDEO.search(text(have)) and not mapping.VIDEO.search(str(wanted)):
                return True
            # The same for a link to the source shop that was turned into plain text
            if mapping.SOURCE_LINK.search(text(have)) and not mapping.SOURCE_LINK.search(str(wanted)):
                return True
        elif isinstance(wanted, Lang):
            if text(have) != str(wanted):
                return True
        elif not _same_value(have, wanted):
            return True
    return False


def _same_value(have: object, wanted: object) -> bool:
    """Compares a value read from the API (always text, left out when empty) with one the importer sends."""
    have_text = "" if have is None else str(have)
    wanted_text = "" if wanted is None else str(wanted)
    try:
        return Decimal(have_text or "0") == Decimal(wanted_text or "0")
    except ArithmeticError:
        return have_text == wanted_text
