"""The import steps. __main__.run() calls them in order; each step does only its own job.

Every step compares what the data says with what the shop already has (read once by read_shop), and
creates, updates or leaves each record alone. That is what makes a second run safe: it finds everything
and changes nothing. The keys used to find existing records are explained in ADR 0008:
- category: its name and its parent in the shop;
- manufacturer: its name;
- product: `reference` = the product ID in the source shop.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from . import mapping
from .api import ApiError, Lang, ShopApi, text
from .report import Report

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
    stock: dict[int, dict]  # product ID -> its stock row
    specific_prices: dict[int, list[dict]]  # product ID -> its specific prices


# --- Step 0: what is already in the shop -------------------------------------------------------------


def read_shop(api: ShopApi) -> Shop:
    roots = api.list("categories", display="[id]", filters={"is_root_category": 1})
    categories = api.list("categories", display="[id,id_parent,name,link_rewrite,active,level_depth]")
    products = api.list("products", display="full")
    stock_rows = api.list("stock_availables", display="full", filters={"id_product_attribute": 0})
    specific_prices: dict[int, list[dict]] = {}
    # Only prices not made by a catalogue price rule: set_promotion deletes the ones it does not want, and
    # prices from a rule belong to that rule (the shop recreates them from it)
    for price in api.list("specific_prices", display="full", filters={"id_specific_price_rule": 0}):
        specific_prices.setdefault(int(price["id_product"]), []).append(price)

    return Shop(
        home_id=int(roots[0]["id"]),
        tax_groups=read_tax_groups(api),
        categories={(int(c["id_parent"]), text(c["name"])): c for c in categories},
        manufacturers={text(m["name"]): m for m in api.list("manufacturers", display="[id,name,active]")},
        products={str(p.get("reference", "")): p for p in products},
        all_products=products,
        stock={int(s["id_product"]): s for s in stock_rows},
        specific_prices=specific_prices,
    )


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
        }
        existing = shop.categories.get((parent, category["name"]))
        try:
            shop_ids[category["id"]] = save("categories", api, existing, fields, report)
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
        with PRODUCT_SAVE:
            saved = save_record("products", api, existing, fields, report)
    except ApiError as error:
        report.reject("products", product["id"], error.message)
        return None
    product_id = int(saved["id"])
    # A product created just now is not in the snapshot: its stock row comes from the create response
    set_stock(api, shop, product, saved, report)
    set_promotion(api, shop.specific_prices.get(product_id, []), product, product_id, report)
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
        "description": Lang(product["description"]),
        "link_rewrite": Lang(mapping.link_rewrite(product["url"], product["name"])),
        "associations": {"categories": [("category", {"id": c}) for c in categories]},
    }


def set_stock(api: ShopApi, shop: Shop, product: dict, saved: dict, report: Report) -> None:
    """Stock 0-10 from the source ID (mapping.stock_quantity). PrestaShop made the row with the product."""
    quantity = mapping.stock_quantity(product["id"])
    product_id = int(saved["id"])
    row = shop.stock.get(product_id)
    if row is None and product_id < 0:
        # --dry-run: the product was not really created, so there is no row
        report.count("stock", "created")
        return
    if row is None:
        # New product: the create response lists the row PrestaShop made for it
        rows = saved.get("associations", {}).get("stock_availables", [])
        row = next((r for r in rows if str(r.get("id_product_attribute", "0")) == "0"), None)
        if row is None:
            report.reject("stock", product["id"], "PrestaShop created no stock row for the product")
            return
        outcome = "created"
    elif int(row["quantity"]) == quantity and int(row["out_of_stock"]) == OUT_OF_STOCK_DEFAULT:
        report.count("stock", "unchanged")
        return
    else:
        outcome = "updated"
    fields = {
        "id_product": product_id,
        "id_product_attribute": 0,
        "id_shop": row.get("id_shop", saved.get("id_shop_default", 1)),
        "id_shop_group": row.get("id_shop_group", 0),
        "quantity": quantity,
        "depends_on_stock": 0,
        "out_of_stock": OUT_OF_STOCK_DEFAULT,
        "location": "",
    }
    try:
        api.update("stock_availables", int(row["id"]), fields)
        report.count("stock", outcome)
    except ApiError as error:
        report.reject("stock", product["id"], error.message)


def promotion_fields(product: dict, product_id: int) -> dict:
    """A specific price that takes the regular gross price down to the promotional one, for everybody, always.

    The reduction is an amount with tax included, so the shop shows exactly the source's promotional price.
    """
    return {
        "id_product": product_id,
        "id_product_attribute": 0,
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


def set_promotion(api: ShopApi, existing: list[dict], product: dict, product_id: int, report: Report) -> None:
    """One specific price per discounted product; none for the others."""
    try:
        if not product["has_discount"]:
            for price in existing:
                api.delete("specific_prices", int(price["id"]))
                report.count("specific_prices", "deleted")
            return
        fields = promotion_fields(product, product_id)
        first, extra = (existing[0], existing[1:]) if existing else (None, [])
        save("specific_prices", api, first, fields, report)
        for price in extra:
            api.delete("specific_prices", int(price["id"]))
            report.count("specific_prices", "deleted")
    except ApiError as error:
        report.reject("specific_prices", product["id"], error.message)


def set_images(api: ShopApi, existing: dict, product: dict, product_id: int, data_dir: Path, report: Report) -> None:
    """Uploads the product's images in the listed order; the first one becomes the cover.

    The shop itself says what is already there: a product with as many images as the data lists is left
    alone. Otherwise its images are replaced, so the order and the cover are right.
    """
    current = [int(i["id"]) for i in existing.get("associations", {}).get("images", [])]
    wanted = product["images"]
    if len(current) == len(wanted):
        report.count("images", "unchanged", len(wanted))
        return
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
        if name == "description":
            if mapping.visible_text(text(have)) != mapping.visible_text(str(wanted)):
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
