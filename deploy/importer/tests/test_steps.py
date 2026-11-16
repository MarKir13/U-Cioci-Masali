"""How the steps decide between create, update and leave alone (no shop needed)."""

from importer.api import Lang
from importer.report import Report
from importer.steps import Shop, differs, remove_other_records

# A product as the API returns it: everything as text, empty fields left out, cleaned description
IN_SHOP = {
    "id": 7,
    "reference": "100",
    "price": "11.780488",
    "weight": "0.030000",
    "id_manufacturer": "3",
    "name": "Kredka",
    "description": '<p><a href="x">Himalaya</a> kredka<br />czarna</p>',
    "associations": {"categories": [{"id": "12"}, {"id": "40"}]},
}

WANTED = {
    "reference": 100,
    "price": "11.780488",
    "weight": 0.03,
    "id_manufacturer": 3,
    "ean13": "",
    "name": Lang("Kredka"),
    "description": Lang('<p><a href="x" rel="pmsil">Himalaya</a> kredka<br>czarna</p>'),
    "associations": {"categories": [("category", {"id": 40}), ("category", {"id": 12})]},
}


def test_the_same_product_does_not_differ():
    assert not differs(IN_SHOP, WANTED)


def test_a_new_price_differs():
    assert differs(IN_SHOP, {**WANTED, "price": "12.000000"})


def test_a_changed_description_text_differs():
    assert differs(IN_SHOP, {**WANTED, "description": Lang("<p>Himalaya kredka niebieska</p>")})


def test_another_category_differs():
    categories = {"categories": [("category", {"id": 12})]}
    assert differs(IN_SHOP, {**WANTED, "associations": categories})


def test_a_new_barcode_differs():
    assert differs(IN_SHOP, {**WANTED, "ean13": "8901138515010"})


# --- The delete step (remove_other_records) ---


class RecordingApi:
    """Stands in for ShopApi: remembers what would be deleted."""

    def __init__(self):
        self.deleted: list[tuple[str, int]] = []

    def delete(self, resource: str, record_id: int) -> None:
        self.deleted.append((resource, record_id))


def shop_after_an_earlier_import() -> Shop:
    """Products 100 and 200 imported before, plus the installer's demo product, category and manufacturer."""
    return Shop(
        home_id=2,
        tax_groups={},
        categories={
            (2, "Kosmetyki"): {"id": "10", "name": "Kosmetyki", "level_depth": "2"},
            (2, "Clothes"): {"id": "3", "name": "Clothes", "level_depth": "2"},
        },
        manufacturers={"Himalaya": {"id": "5"}, "Studio Design": {"id": "1"}},
        products={},
        all_products=[
            {"id": "7", "reference": "100"},
            {"id": "8", "reference": "200"},
            {"id": "1", "reference": "demo_1"},
        ],
        stock={},
        specific_prices={},
    )


def test_a_full_run_deletes_what_is_not_in_the_data():
    api = RecordingApi()
    products = [{"id": 100}, {"id": 200}]
    remove_other_records(api, shop_after_an_earlier_import(), products, set(), {8: 10}, {"Himalaya": 5}, Report())
    assert api.deleted == [("products", 1), ("categories", 3), ("manufacturers", 1)]


def test_a_rejected_product_keeps_its_copy_in_the_shop():
    # Product 200 was rejected this time (for example its image file is missing): it is still in the data
    api = RecordingApi()
    report = Report()
    report.reject("products", 200, "image file missing")
    remove_other_records(api, shop_after_an_earlier_import(), [{"id": 100}], {200}, {8: 10}, {"Himalaya": 5}, report)
    # Only the demo product and category; no manufacturer, since product 200's brand is unknown
    assert api.deleted == [("products", 1), ("categories", 3)]


def test_a_rejected_category_stops_deleting_categories():
    api = RecordingApi()
    report = Report()
    report.reject("categories", 8, "HTTP 500")
    remove_other_records(api, shop_after_an_earlier_import(), [{"id": 100}, {"id": 200}], set(), {}, {}, report)
    assert ("products", 1) in api.deleted
    assert not [d for d in api.deleted if d[0] == "categories"]


def test_an_unreadable_line_stops_deleting_products_and_manufacturers():
    # Line 2 of products.jsonl could not be read: it may be product 200, whose copy must stay
    api = RecordingApi()
    report = Report()
    report.reject("products", "products.jsonl line 2", "not valid JSON")
    remove_other_records(
        api,
        shop_after_an_earlier_import(),
        [{"id": 100}],
        set(),
        {8: 10},
        {"Himalaya": 5},
        report,
        all_lines_read=False,
    )
    # Only the demo category: no product (not even the demo one) and no manufacturer
    assert api.deleted == [("categories", 3)]
