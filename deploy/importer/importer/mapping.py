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

# A video player in a description, from <video to </video>, across lines and in any letter case (see without_videos)
VIDEO = re.compile(r"<video\b.*?</video\s*>", re.IGNORECASE | re.DOTALL)

# A link to the source shop, <a href="https://www.magiczne-indie.pl/...">text</a>; group 2 is the link text
# (see without_source_links)
SOURCE_LINK = re.compile(
    r"<a\b[^>]*?\bhref\s*=\s*([\"'])https?://(?:www\.)?magiczne-indie\.pl\b[^\"']*\1[^>]*>(.*?)</a\s*>",
    re.IGNORECASE | re.DOTALL,
)


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


def variant_quantities(source_ids: list[int]) -> list[int]:
    """Stock of each combination of a product with variants, in the order of `source_ids`.

    Each variant starts from its source product's stock (stock_quantity). The product's own stock is the sum of
    its combinations, and the course checks that no product has more than MAX_STOCK, so when the sum is above it,
    every quantity is scaled down in proportion (rounded down): 2 + 7 + 9 = 18 becomes 1 + 3 + 5 = 9. A variant
    with 0 stays at 0, so a sold-out variant stays sold out. If the scaling leaves nothing in stock while a
    source product had some, the variant with the most gets 1.
    """
    quantities = [stock_quantity(i) for i in source_ids]
    total = sum(quantities)
    if total <= MAX_STOCK:
        return quantities
    scaled = [q * MAX_STOCK // total for q in quantities]
    if not any(scaled):
        scaled[quantities.index(max(quantities))] = 1
    return scaled


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
    from_url = re.sub(r"^\d+-", "", last)
    if LINK_REWRITE.match(from_url):
        return from_url[:128]
    return slug(name)


def slug(name: str) -> str:
    """A URL slug made from a name: lowercase ASCII words joined by hyphens, such as `krem-oliwkowy`."""
    ascii_name = name.translate(POLISH_TO_ASCII).lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:128] or "produkt"


def price_impact(regular_price: str, default_regular_price: str, vat_rate: float) -> str:
    """A combination's price as PrestaShop stores it: the difference to the product's net price (its "impact").

    The product holds the default variant's net price, so the default combination's impact is 0. Both net prices
    have 6 decimals, so the product's price plus the impact is the variant's own net price exactly, and the shop
    shows the variant's gross price from the source.
    """
    impact = Decimal(net_price(regular_price, vat_rate)) - Decimal(net_price(default_regular_price, vat_rate))
    return str(impact.quantize(NET_PLACES))


def weight_impact(weight: dict | None, default_weight: dict | None) -> float:
    """A combination's weight as PrestaShop stores it: the difference to the product's weight, in kilograms."""
    return round(weight_kg(weight) - weight_kg(default_weight), 6)


def value_order(value: str) -> tuple[float, str]:
    """Sort key for attribute values: by the first number in them, so "8 g" comes before "50 g" and "100 g".

    Values without a number come last, in alphabetical order.
    """
    number = re.search(r"\d+(?:[.,]\d+)?", value)
    return (float(number.group().replace(",", ".")) if number else float("inf"), value)


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


def without_videos(html: str) -> str:
    """A description without its video players, so it sends no request for a file the shop does not have.

    Seven source descriptions (Tibetan singing bowls) play videos from the source shop's /img/cms/ through a
    relative address, such as <source src="/img/cms/20220719_150939.mp4">. In our shop that address answers 404,
    because the files were never scraped. The players hold no text, so what a customer reads stays the same.
    Images from the source shop are kept: they load from there.
    """
    return VIDEO.sub("", html)


def descriptions(product: dict) -> tuple[str, str]:
    """The long description (the product page's description tab) and the short one (above "Add to cart").

    A product whose long description is empty on the source has its short one in `description` too, because the
    scraper falls back to it (ADR 0007). The source shows that text only above the button, so the shop gets the
    same: an empty long description, which PrestaShop does not show. A product without a short description
    gets an empty one.
    """
    long = without_videos(product["description"])
    short = without_videos(product.get("description_short") or "")
    if short and visible_text(short) == visible_text(long):
        return "", short
    return long, short


def without_source_links(html: str) -> str:
    """A description with the links to the source shop turned into plain text.

    The descriptions of the copper vessel categories (399, 464) point to sibling categories and to an article on
    the source shop, so a click would take a customer out of our shop to the real one. The article has no
    counterpart here and the category ids differ between shops, so the link text stays and the address goes.
    """
    return SOURCE_LINK.sub(r"\2", html)


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
