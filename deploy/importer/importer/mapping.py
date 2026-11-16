"""Pure functions that turn scraped values into the values the shop stores.

No network and no shop here, so every rule can be unit-tested (tests/test_mapping.py).
The reasons for the rules are in docs/adr/0008-product-import-through-the-webservice-api.md.
"""

import hashlib
import re
from decimal import ROUND_HALF_UP, Decimal
from html import unescape

# PrestaShop keeps net prices with 6 decimals and rounds gross prices to the grosz, half up
# (PS_PRICE_ROUND_MODE = 2).
NET_PLACES = Decimal("0.000001")
GROSZ = Decimal("0.01")

# Raw weights below this, written with decimals, are already kilograms (see weight_kg)
KG_BELOW = 5

# Share of products with stock 0: one in OUT_OF_STOCK_ONE_IN (10%, the brief allows 5-20%)
OUT_OF_STOCK_ONE_IN = 10
MAX_STOCK = 10

# What PrestaShop accepts as a link rewrite (Validate::isLinkRewrite without accented characters)
LINK_REWRITE = re.compile(r"^[_a-zA-Z0-9-]+$")
POLISH_TO_ASCII = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def net_price(gross: str, vat_rate: float) -> str:
    """The net price PrestaShop stores for a gross price, with 6 decimals.

    The source shows gross prices; PrestaShop stores net ones and adds VAT when it shows them.
    Six decimals are enough for net x (1 + VAT), rounded to the grosz, to give back `gross` exactly.
    """
    net = Decimal(gross) / (1 + Decimal(str(vat_rate)) / 100)
    return str(net.quantize(NET_PLACES, rounding=ROUND_HALF_UP))


def gross_price(net: str, vat_rate: float) -> str:
    """The gross price the shop shows for a stored net price, the way PrestaShop rounds it."""
    gross = Decimal(net) * (1 + Decimal(str(vat_rate)) / 100)
    return str(gross.quantize(GROSZ, rounding=ROUND_HALF_UP))


def promotion_amount(regular_price: str, price: str) -> str:
    """The discount, gross, that takes the regular price down to the promotional one."""
    return str((Decimal(regular_price) - Decimal(price)).quantize(GROSZ))


def weight_kg(raw: dict | None) -> float:
    """Weight in kilograms from the raw source weight, or 0 without one.

    The source labels every weight "g", but some values are kilograms. A value below 5 with decimals
    is read as kilograms (0.04 is a 40 g bottle, 1.3 a 1.3 kg candle holder); everything else, including
    whole numbers such as 1.0 (foil gloves), is grams.
    """
    if raw is None:
        return 0.0
    value = float(raw["value"])
    if value < KG_BELOW and not value.is_integer():
        return round(value, 6)
    return round(value / 1000, 6)


def stock_quantity(source_id: int) -> int:
    """Stock from 0 to 10, the same on every run and spread like random numbers.

    h is a SHA-256 fingerprint of the source ID read as a number. Its last digit is 0 for about one
    product in ten: those get 0. Otherwise the digit before it, 0-9, plus 1 gives 1-10.
    Not Python's hash(), which gives different values every time Python starts.
    """
    h = int.from_bytes(hashlib.sha256(str(source_id).encode()).digest()[:8], "big")
    if h % OUT_OF_STOCK_ONE_IN == 0:
        return 0
    return 1 + (h // OUT_OF_STOCK_ONE_IN) % MAX_STOCK


def ean_check_digit_ok(code: str) -> bool:
    """GTIN check digit (EAN-13, EAN-8, UPC-A): digits weighted 3 and 1 from the right."""
    digits = [int(c) for c in code]
    body = digits[:-1][::-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(body))
    return (10 - total % 10) % 10 == digits[-1]


def barcodes(ean: str | None) -> tuple[str, str]:
    """(ean13, upc) for the shop: 13 or 8 digits are an EAN, 12 digits a UPC. Invalid codes are dropped."""
    if not ean or not ean.isdigit() or not ean_check_digit_ok(ean):
        return "", ""
    if len(ean) in (8, 13):
        return ean, ""
    if len(ean) == 12:
        return "", ean
    return "", ""


def link_rewrite(url: str, name: str) -> str:
    """The URL slug from the source, such as `kosmetyki-do-wlosow` from `.../38-kosmetyki-do-wlosow`.

    Falls back to the name, written in ASCII, if the source slug is not valid in PrestaShop.
    """
    last = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
    slug = re.sub(r"^\d+-", "", last)
    if LINK_REWRITE.match(slug):
        return slug[:128]
    ascii_name = name.translate(POLISH_TO_ASCII).lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:128] or "produkt"


def visible_text(html: str) -> str:
    """The characters a customer reads in an HTML description: no tags, entities decoded, no whitespace at all.

    PrestaShop cleans every description on save (HTMLPurifier): it drops unknown attributes and empty tags, writes
    `&` as `&amp;` and `<br>` as `<br />`, and removes embedded `data:` images. A description read back from the shop
    therefore never equals the source HTML, but its visible characters do, so that is what the importer compares.
    Whitespace is left out completely, because a removed tag between two characters ("W<span></span>.") would
    otherwise count as a change.
    """
    without_tags = re.sub(r"<[^>]*>", " ", html)
    return "".join(unescape(without_tags).split())


def parents_first(categories: list[dict]) -> list[dict]:
    """Categories ordered so that every parent comes before its children (top-level first)."""
    by_id = {c["id"]: c for c in categories}

    def depth(category: dict) -> int:
        level = 0
        while category["parent_id"] is not None:
            category = by_id[category["parent_id"]]
            level += 1
        return level

    return sorted(categories, key=depth)


def with_descendants(category_ids: set[int], categories: list[dict]) -> set[int]:
    """The given source category IDs plus all their subcategories (for --categories)."""
    result = set(category_ids)
    changed = True
    while changed:
        changed = False
        for category in categories:
            if category["parent_id"] in result and category["id"] not in result:
                result.add(category["id"])
                changed = True
    return result
