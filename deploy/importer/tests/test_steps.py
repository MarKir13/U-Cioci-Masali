"""How the steps decide between create, update and leave alone (no shop needed)."""

from importer.api import Lang
from importer.report import Report
from importer.steps import (
    Shop,
    differs,
    import_categories,
    read_shop,
    remove_other_records,
)
from tests.fake_shop import FakeApi

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


def test_a_video_left_in_the_shop_differs():
    # Imported before the importer removed video players: same text, but the shop still has the player
    video = '<video controls="controls"><source src="/img/cms/a.mp4" type="video/mp4" /></video>'
    in_shop = {
        **IN_SHOP,
        "description": IN_SHOP["description"].replace("</p>", f"{video}</p>"),
    }
    assert differs(in_shop, WANTED)


def test_a_source_link_left_in_the_shop_differs():
    # Imported before the importer turned source links into text: same words, but the shop still has the link
    link = '<a href="https://www.magiczne-indie.pl/399-x">Himalaya</a>'
    in_shop = {**IN_SHOP, "description": f"<p>{link} kredka<br />czarna</p>"}
    assert differs(in_shop, {**WANTED, "description": Lang("<p>Himalaya kredka<br>czarna</p>")})


def test_a_source_link_the_importer_keeps_does_not_differ():
    # Product descriptions keep their links, so the same link in the shop is not a change
    link = '<a href="https://www.magiczne-indie.pl/399-x">Himalaya</a>'
    in_shop = {**IN_SHOP, "description": f"<p>{link} kredka<br />czarna</p>"}
    assert not differs(in_shop, {**WANTED, "description": Lang(f"<p>{link} kredka<br>czarna</p>")})


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
    remove_other_records(
        api,
        shop_after_an_earlier_import(),
        products,
        set(),
        {8: 10},
        {"Himalaya": 5},
        Report(),
    )
    assert api.deleted == [("products", 1), ("categories", 3), ("manufacturers", 1)]


def test_a_rejected_product_keeps_its_copy_in_the_shop():
    # Product 200 was rejected this time (for example its image file is missing): it is still in the data
    api = RecordingApi()
    report = Report()
    report.reject("products", 200, "image file missing")
    remove_other_records(
        api,
        shop_after_an_earlier_import(),
        [{"id": 100}],
        {200},
        {8: 10},
        {"Himalaya": 5},
        report,
    )
    # Only the demo product and category; no manufacturer, since product 200's brand is unknown
    assert api.deleted == [("products", 1), ("categories", 3)]


def test_a_rejected_category_stops_deleting_categories():
    api = RecordingApi()
    report = Report()
    report.reject("categories", 8, "HTTP 500")
    remove_other_records(
        api,
        shop_after_an_earlier_import(),
        [{"id": 100}, {"id": 200}],
        set(),
        {},
        {},
        report,
    )
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


def test_category_description_is_imported_and_a_second_run_changes_nothing():
    api = FakeApi()
    categories = [
        {
            "id": 8,
            "name": "Kosmetyki",
            "url": "https://www.magiczne-indie.pl/8-kosmetyki",
            "parent_id": None,
            "description": "<p>Tylko u nas kupisz naturalne henny.</p>",
        },
        {
            "id": 36,
            "name": "Higiena",
            "url": "https://www.magiczne-indie.pl/36-higiena",
            "parent_id": 8,
            "description": None,
        },
    ]
    import_categories(api, read_shop(api), categories, Report())
    by_name = {c["name"]: c for c in api.all("categories")}
    assert by_name["Kosmetyki"]["description"] == "<p>Tylko u nas kupisz naturalne henny.</p>"
    assert by_name["Higiena"]["description"] == ""

    writes_before = len(api.writes)
    import_categories(api, read_shop(api), categories, Report())
    assert len(api.writes) == writes_before

    # Source text changed: the shop's description is updated, not duplicated
    categories[0]["description"] = "<p>Nowy opis.</p>"
    import_categories(api, read_shop(api), categories, Report())
    assert [c["description"] for c in api.all("categories") if c["name"] == "Kosmetyki"] == ["<p>Nowy opis.</p>"]
    assert len([c for c in api.all("categories") if c["name"] == "Kosmetyki"]) == 1


# --- Category positions: the order among siblings, as on the source ----------------------------------


def kosmetyki_tree() -> list[dict]:
    """Kosmetyki with three of its subcategories, in the source order 360, 37, 36 (not the order of their ids)."""

    def category(category_id: int, name: str, parent_id: int | None, position: int | None) -> dict:
        url = f"https://www.magiczne-indie.pl/{category_id}-k"
        return {"id": category_id, "name": name, "url": url, "parent_id": parent_id, "position": position}

    return [
        category(8, "Kosmetyki", None, 1),
        category(36, "Higiena i akcesoria", 8, 3),
        category(37, "Do ciała", 8, 2),
        category(360, "Kosmetyki BIO", 8, 1),
    ]


def shop_positions(api: FakeApi) -> dict[str, str]:
    return {c["name"]: c["position"] for c in api.all("categories") if c["name"] != "Strona główna"}


def test_new_categories_get_the_source_position_counted_from_0():
    api = FakeApi()
    report = Report()
    import_categories(api, read_shop(api), kosmetyki_tree(), report)
    assert shop_positions(api) == {"Kosmetyki": "0", "Higiena i akcesoria": "2", "Do ciała": "1", "Kosmetyki BIO": "0"}
    # The shop puts a new category last, so the ones it put elsewhere get an update right after being created.
    # They count as created only: the update is part of creating them.
    assert report.counts["categories"] == {"created": 4}


def test_a_wrong_position_in_the_shop_is_updated_and_a_second_run_changes_nothing():
    api = FakeApi()
    import_categories(api, read_shop(api), kosmetyki_tree(), Report())
    # As after an import from before positions were scraped: Do ciała where the shop put it
    do_ciala = next(c for c in api.all("categories") if c["name"] == "Do ciała")
    do_ciala["position"] = "5"

    report = Report()
    import_categories(api, read_shop(api), kosmetyki_tree(), report)
    assert shop_positions(api)["Do ciała"] == "1"
    assert report.counts["categories"] == {"updated": 1, "unchanged": 3}

    writes_before = len(api.writes)
    report = Report()
    import_categories(api, read_shop(api), kosmetyki_tree(), report)
    assert len(api.writes) == writes_before
    assert report.counts["categories"] == {"unchanged": 4}


def test_a_category_without_a_position_stays_where_the_shop_put_it():
    """Data from before positions were scraped: no position is sent, so the shop's order is kept."""
    api = FakeApi()
    tree = [{**c, "position": None} for c in kosmetyki_tree()]
    import_categories(api, read_shop(api), tree, Report())
    assert shop_positions(api) == {"Kosmetyki": "0", "Higiena i akcesoria": "0", "Do ciała": "1", "Kosmetyki BIO": "2"}
    assert ("PUT", "categories") not in api.writes
