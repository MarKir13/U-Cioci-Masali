"""Products with variants (importer/variants.py and the variant steps), without a shop.

The step tests run against tests/fake_shop.py, an in-memory stand-in for the API. They check the importer's own
logic (what it finds, what it writes, what it leaves alone); whether PrestaShop accepts the records is checked
on a running shop (deploy/importer/README.md).
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fake_shop import FakeApi

from importer import mapping, steps, variants
from importer.report import Report

RESULTS = Path(__file__).resolve().parents[3] / "scraper-results"


def source_product(source_id: int, size: str, price: str, regular_price: str | None = None, **extra) -> dict:
    """A product as in products.jsonl, with two images."""
    return {
        "id": source_id,
        "url": f"https://www.magiczne-indie.pl/{source_id}-krem-{size}.html",
        "name": f"Krem {size} Himalaya",
        "description": f"<p>Krem {size}</p>",
        "price": price,
        "regular_price": regular_price or price,
        "has_discount": regular_price is not None,
        "vat_rate": 23.0,
        "brand": None,
        "ean": None,
        "weight": None,
        "category_ids": [94],
        "images": [{"local_path": f"images/{source_id}-{n}.jpg"} for n in (1, 2)],
        **extra,
    }


SMALL = source_product(7392, "50ml", "8.95", ean="8901138506377")
LARGE = source_product(120, "150ml", "16.44", weight={"value": "194.000000", "unit": "g"}, ean="8901138506384")
# Discounted in the source: 17.66 instead of 19.62
EXTRA = source_product(8701, "250ml", "17.66", "19.62")


def definition(*sources: tuple[str, dict], name: str = "Krem odżywczy Himalaya", group: str = "Pojemność") -> dict:
    return {
        "name": name,
        "attribute_group": group,
        "values": [{"value": value, "source_id": p["id"]} for value, p in sources],
    }


TWO_SIZES = definition(("50 ml", SMALL), ("150 ml", LARGE))
THREE_SIZES = definition(("50 ml", SMALL), ("150 ml", LARGE), ("250 ml", EXTRA))
ALL = [SMALL, LARGE, EXTRA]


# --- variants.json: reading and checking ---


def test_a_valid_entry_keeps_its_order():
    products, rejected = variants.resolve([TWO_SIZES], ALL)
    assert rejected == []
    [product] = products
    assert [v.value for v in product.variants] == ["50 ml", "150 ml"]
    assert product.default is SMALL
    assert product.source_ids == {7392, 120}


@pytest.mark.parametrize(
    ("entry", "reason"),
    [
        (definition(("50 ml", SMALL)), "values"),  # one value only
        ({**TWO_SIZES, "colour": "red"}, "Additional properties"),
        (definition(("50 ml", SMALL), ("50 ml", LARGE)), "a value is listed twice"),
        (definition(("50 ml", SMALL), ("150 ml", SMALL)), "a source product is listed twice"),
        (definition(("50 ml", SMALL), ("150 ml", {"id": 999})), "not in the data or rejected: 999"),
    ],
)
def test_an_invalid_entry_is_rejected_with_its_reason(entry, reason):
    products, rejected = variants.resolve([entry], ALL)
    assert products == []
    assert len(rejected) == 1
    assert reason in rejected[0][1]


def test_a_source_product_can_be_in_one_entry_only():
    second = definition(("150 ml", LARGE), ("250 ml", EXTRA), name="Inny krem")
    products, rejected = variants.resolve([TWO_SIZES, second], ALL)
    assert [p.name for p in products] == ["Krem odżywczy Himalaya"]
    assert rejected == [("Inny krem", "source product(s) already used by an earlier entry: 120")]


def test_variants_must_have_the_same_vat():
    other_vat = {**LARGE, "vat_rate": 8.0}
    _, rejected = variants.resolve([TWO_SIZES], [SMALL, other_vat])
    assert rejected == [("Krem odżywczy Himalaya", "the source products have different VAT rates")]


def test_a_missing_file_means_no_variants(tmp_path):
    assert variants.load(tmp_path / "variants.json") == []


def test_a_file_without_a_product_list_stops_the_import(tmp_path):
    path = tmp_path / "variants.json"
    path.write_text('{"items": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="products"):
        variants.load(path)


def test_the_product_record_joins_the_variants():
    large = {**LARGE, "category_ids": [94, 45]}
    [product], _ = variants.resolve([definition(("50 ml", SMALL), ("150 ml", large))], [SMALL, large])
    record = variants.product_record(product)
    assert record["id"] == 7392  # the default variant's source ID: how the next run finds the product
    assert record["name"] == "Krem odżywczy Himalaya"
    assert record["link_rewrite"] == "krem-odzywczy-himalaya"
    assert record["category_ids"] == [94, 45]
    # The default variant's images first, so its first image is the cover
    assert [i["local_path"] for i in record["images"]][:2] == ["images/7392-1.jpg", "images/7392-2.jpg"]
    assert len(record["images"]) == 4
    assert record["ean"] is None
    assert record["has_discount"] is False


def test_values_are_listed_smallest_number_first():
    bollywood = definition(("8 g", SMALL), ("100 g", LARGE), ("50 g", EXTRA), group="Waga")
    products, _ = variants.resolve([bollywood], ALL)
    assert variants.values_by_group(products) == {"Waga": ["8 g", "50 g", "100 g"]}


def test_the_real_variants_file_is_valid():
    path = variants.DEFAULT_PATH
    products_file = RESULTS / "products.jsonl"
    if not products_file.is_file():
        pytest.skip("scraper-results/products.jsonl not found")
    products = [json.loads(line) for line in products_file.open(encoding="utf-8") if line.strip()]
    found, rejected = variants.resolve(variants.load(path), products)
    assert rejected == []
    # D3 asks for at least 5 products with at least 2 variants; the file has one more as a spare
    assert len(found) >= 6
    assert all(len(p.variants) >= 2 for p in found)
    for product in found:
        # Every variant is linked to the default one by the source shop's ndx-family module (in one direction or
        # the other: the source does not always list the link on both products)
        default = product.default
        for variant in product.variants[1:]:
            linked = variant.product["url"] in default["family"] or default["url"] in variant.product["family"]
            assert linked, (product.name, variant.value)


# --- Prices and weights of combinations ---


def test_a_combination_price_is_the_net_difference_and_gives_back_the_source_price():
    impact = mapping.price_impact("16.44", "8.95", 23.0)
    assert impact == "6.089431"
    base = Decimal(mapping.net_price("8.95", 23.0))
    assert mapping.gross_price(str(base + Decimal(impact)), 23.0) == "16.44"


def test_the_default_combination_has_no_price_or_weight_difference():
    assert mapping.price_impact("8.95", "8.95", 23.0) == "0.000000"
    assert mapping.weight_impact(None, None) == 0.0


def test_a_combination_weight_is_the_difference_in_kilograms():
    assert mapping.weight_impact({"value": "194.000000", "unit": "g"}, None) == 0.194
    assert mapping.weight_impact(None, {"value": "194.000000", "unit": "g"}) == -0.194


def test_every_real_combination_gives_back_its_source_price():
    if not (RESULTS / "products.jsonl").is_file():
        pytest.skip("scraper-results/products.jsonl not found")
    products = [json.loads(line) for line in (RESULTS / "products.jsonl").open(encoding="utf-8") if line.strip()]
    found, _ = variants.resolve(variants.load(variants.DEFAULT_PATH), products)
    for product in found:
        default = product.default
        base = Decimal(mapping.net_price(default["regular_price"], default["vat_rate"]))
        for variant in product.variants:
            impact = mapping.price_impact(
                variant.product["regular_price"], default["regular_price"], default["vat_rate"]
            )
            gross = mapping.gross_price(str(base + Decimal(impact)), default["vat_rate"])
            assert Decimal(gross) == Decimal(variant.product["regular_price"]), (product.name, variant.value)


# --- Stock of combinations ---


def test_variant_stock_is_the_source_stock_when_the_sum_is_at_most_10():
    # Pasta Dant Kanti would be 9 + 10, Mysore 6 + 4
    assert mapping.variant_quantities([5212, 5211]) == [mapping.stock_quantity(5212), mapping.stock_quantity(5211)]
    assert sum(mapping.variant_quantities([5212, 5211])) == 10


def test_variant_stock_is_scaled_down_when_the_sum_is_above_10():
    # Bollywood: the source products have 2 + 7 + 9 = 18
    assert [mapping.stock_quantity(i) for i in (7736, 8347, 8345)] == [2, 7, 9]
    assert mapping.variant_quantities([7736, 8347, 8345]) == [1, 3, 5]


def test_a_sold_out_variant_stays_sold_out_and_one_variant_keeps_stock(monkeypatch):
    stock = {1: 0, 2: 10, 3: 10, 4: 10}
    monkeypatch.setattr(mapping, "stock_quantity", stock.get)
    assert mapping.variant_quantities([1, 2, 3, 4]) == [0, 3, 3, 3]
    # Twelve variants with 1 each: 1 * 10 // 12 = 0 for all, so the first gets 1
    monkeypatch.setattr(mapping, "stock_quantity", lambda _: 1)
    assert mapping.variant_quantities(list(range(12))) == [1] + [0] * 11


def test_every_real_product_with_variants_has_at_most_10_in_stock():
    if not (RESULTS / "products.jsonl").is_file():
        pytest.skip("scraper-results/products.jsonl not found")
    products = [json.loads(line) for line in (RESULTS / "products.jsonl").open(encoding="utf-8") if line.strip()]
    found, _ = variants.resolve(variants.load(variants.DEFAULT_PATH), products)
    for product in found:
        source_ids = [v.product["id"] for v in product.variants]
        quantities = mapping.variant_quantities(source_ids)
        # "Maximum stock <= 10 for every product and variant": the product's row is the sum
        assert sum(quantities) <= mapping.MAX_STOCK, (product.name, quantities)
        assert any(quantities), product.name
        # A source product with 0 stays at 0 (Indian Summer 50 g, 8486: the variant that cannot be ordered)
        for source_id, quantity in zip(source_ids, quantities, strict=True):
            if mapping.stock_quantity(source_id) == 0:
                assert quantity == 0, (product.name, source_id)
    assert mapping.stock_quantity(8486) == 0
    assert 8486 in {i for p in found for i in p.source_ids}


# --- The import steps, on the fake shop ---


class Catalogue:
    """The fake shop with one category, and what one import of the variant products did."""

    def __init__(self) -> None:
        self.api = FakeApi()
        self.category_id = self.api.add("categories", {"id_parent": str(self.api.home_id), "name": "Kremy"})

    def import_variants(self, *entries: dict, products: list[dict] = ALL) -> Report:
        report = Report()
        shop = steps.read_shop(self.api)
        found, rejected = variants.resolve(list(entries), products)
        assert rejected == []
        self.api.writes.clear()
        steps.import_variant_products(self.api, shop, found, {94: self.category_id}, {}, Path("."), report)
        assert report.rejected == 0, report.summary()
        return report

    def import_plain(self, product: dict) -> Report:
        report = Report()
        shop = steps.read_shop(self.api)
        steps.import_product(self.api, shop, product, {94: self.category_id}, {}, report)
        steps.set_images(
            self.api, shop.products.get(str(product["id"])) or {}, product, self.product_id(product), Path("."), report
        )
        return report

    def product_id(self, source: dict) -> int:
        return next(int(p["id"]) for p in self.api.all("products") if p["reference"] == str(source["id"]))

    def combinations(self) -> dict[str, dict]:
        """Reference (source ID) -> combination."""
        return {c["reference"]: c for c in self.api.all("combinations")}

    def stock(self, product_id: int, combination_id: int = 0) -> int:
        rows = self.api.list("stock_availables", filters={"id_product": product_id})
        return next(int(r["quantity"]) for r in rows if r["id_product_attribute"] == str(combination_id))


def test_the_first_import_makes_one_product_with_a_combination_per_variant():
    shop = Catalogue()
    report = shop.import_variants(TWO_SIZES)

    [product] = shop.api.all("products")
    assert product["reference"] == "7392"
    assert product["name"] == "Krem odżywczy Himalaya"
    assert product["price"] == mapping.net_price("8.95", 23.0)
    combinations = shop.combinations()
    assert set(combinations) == {"7392", "120"}
    assert combinations["7392"]["default_on"] == "1"
    assert product["id_default_combination"] == combinations["7392"]["id"]
    assert combinations["120"]["price"] == mapping.price_impact("16.44", "8.95", 23.0)
    assert combinations["120"]["ean13"] == "8901138506384"
    assert combinations["120"]["weight"] == "0.194"
    # Each combination has the images of its own source product: the product's 3rd and 4th
    images = [i["id"] for i in product["associations"]["images"]]
    assert [i["id"] for i in combinations["7392"]["associations"]["images"]] == images[:2]
    assert [i["id"] for i in combinations["120"]["associations"]["images"]] == images[2:]
    # Each combination has its own stock, and the product's own row is their sum
    product_id = int(product["id"])
    small = shop.stock(product_id, int(combinations["7392"]["id"]))
    large = shop.stock(product_id, int(combinations["120"]["id"]))
    assert (small, large) == (mapping.stock_quantity(7392), mapping.stock_quantity(120))
    assert shop.stock(product_id) == small + large
    assert report.counts["combinations"]["created"] == 2
    assert report.counts["product_options"]["created"] == 1
    assert report.counts["product_option_values"]["created"] == 2


def test_a_second_import_changes_nothing():
    shop = Catalogue()
    shop.import_variants(THREE_SIZES)
    report = shop.import_variants(THREE_SIZES)
    assert shop.api.writes == []
    for resource in ("products", "combinations", "stock", "specific_prices", "product_option_values"):
        counts = report.counts[resource]
        assert counts["created"] == counts["updated"] == counts["deleted"] == 0, resource


def test_a_value_added_to_the_file_adds_one_combination():
    shop = Catalogue()
    shop.import_variants(TWO_SIZES)
    report = shop.import_variants(THREE_SIZES)
    assert report.counts["combinations"]["created"] == 1
    assert report.counts["product_option_values"]["created"] == 1
    assert len(shop.api.all("products")) == 1
    assert set(shop.combinations()) == {"7392", "120", "8701"}
    # And the run after that changes nothing again
    shop.import_variants(THREE_SIZES)
    assert shop.api.writes == []


def test_a_value_taken_out_of_the_file_loses_its_combination():
    shop = Catalogue()
    shop.import_variants(THREE_SIZES)
    report = shop.import_variants(TWO_SIZES)
    assert report.counts["combinations"]["deleted"] == 1
    assert set(shop.combinations()) == {"7392", "120"}


def test_a_discounted_variant_gets_its_own_promotion_and_the_product_none():
    shop = Catalogue()
    # Before variants.json, the default variant was a product of its own, discounted
    shop.import_plain({**SMALL, "price": "7.95", "has_discount": True})
    assert [p["id_product_attribute"] for p in shop.api.all("specific_prices")] == ["0"]

    shop.import_variants(THREE_SIZES)
    [promotion] = shop.api.all("specific_prices")
    assert promotion["id_product_attribute"] == shop.combinations()["8701"]["id"]
    assert promotion["reduction"] == "1.96"
    # The same product, found by the default variant's source ID, now with a new name and combinations
    [product] = shop.api.all("products")
    assert product["name"] == "Krem odżywczy Himalaya"


def test_a_product_with_much_stock_in_its_source_products_stays_at_10_or_less():
    sachets = [source_product(i, f"{i}g", "9.99") for i in (7736, 8347, 8345)]  # source stock 2 + 7 + 9
    entry = definition(("8 g", sachets[0]), ("50 g", sachets[1]), ("100 g", sachets[2]), group="Waga")
    shop = Catalogue()
    shop.import_variants(entry, products=sachets)
    product_id = shop.product_id(sachets[0])
    combinations = shop.combinations()
    assert [shop.stock(product_id, int(combinations[str(i)]["id"])) for i in (7736, 8347, 8345)] == [1, 3, 5]
    assert shop.stock(product_id) == 9


def test_a_product_taken_out_of_the_file_loses_its_combinations():
    shop = Catalogue()
    shop.import_variants(TWO_SIZES)
    product_id = shop.product_id(SMALL)
    shop.import_plain(SMALL)
    assert shop.api.all("combinations") == []
    assert shop.stock(product_id) == mapping.stock_quantity(SMALL["id"])
