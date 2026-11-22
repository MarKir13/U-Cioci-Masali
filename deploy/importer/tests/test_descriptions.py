"""The long and the short description of a product: how they are compared and imported (no shop needed)."""

from fake_shop import FakeApi

from importer import steps
from importer.api import Lang
from importer.report import Report

# A product as the API returns it (cleaned HTML), and the fields the importer would send for it
IN_SHOP = {
    "id": 7,
    "reference": "100",
    "description": "<p>Kredka<br />czarna</p>",
    "description_short": "<p>Miękka &amp; trwała</p>",
}
WANTED = {
    "reference": 100,
    "description": Lang("<p>Kredka<br>czarna</p>"),
    "description_short": Lang("<p>Miękka & trwała</p>"),
}


def test_the_same_short_description_does_not_differ():
    # PrestaShop writes & as &amp; on save: only the visible text counts
    assert not steps.differs(IN_SHOP, WANTED)


def test_a_changed_short_description_differs():
    assert steps.differs(IN_SHOP, {**WANTED, "description_short": Lang("<p>Twarda</p>")})


def test_a_short_description_added_to_the_data_differs():
    # A shop imported before the field existed has an empty one
    in_shop = {**IN_SHOP, "description_short": ""}
    assert steps.differs(in_shop, WANTED)
    assert not steps.differs(in_shop, {**WANTED, "description_short": Lang("")})


# --- A whole product on the fake shop: create, update, unchanged ---


def scraped_product(**fields) -> dict:
    """A record of products.jsonl with only what import_product reads."""
    return {
        "id": 100,
        "url": "https://www.magiczne-indie.pl/100-kredka.html",
        "name": "Kredka",
        "description": "<p>Długi opis</p>",
        "description_short": "<p>Krótki opis</p>",
        "price": "14.49",
        "regular_price": "14.49",
        "has_discount": False,
        "vat_rate": 23.0,
        "category_ids": [94],
        **fields,
    }


class Catalogue:
    """The fake shop with one category."""

    def __init__(self) -> None:
        self.api = FakeApi()
        self.category_id = self.api.add("categories", {"id_parent": str(self.api.home_id), "name": "Kredki"})

    def import_product(self, product: dict) -> Report:
        report = Report()
        self.api.writes.clear()
        shop = steps.read_shop(self.api)
        assert steps.import_product(self.api, shop, product, {94: self.category_id}, {}, report) is not None
        return report

    def saved(self) -> tuple[str, str]:
        [product] = self.api.all("products")
        return product["description"], product["description_short"]


def test_the_short_description_is_created_then_left_alone():
    shop = Catalogue()
    assert shop.import_product(scraped_product()).counts["products"]["created"] == 1
    assert shop.saved() == ("<p>Długi opis</p>", "<p>Krótki opis</p>")

    assert shop.import_product(scraped_product()).counts["products"]["unchanged"] == 1
    assert shop.api.writes == []


def test_a_short_description_new_in_the_data_updates_the_product_once():
    # Imported before the scraper saved the field (products.jsonl without it)
    shop = Catalogue()
    old = scraped_product()
    del old["description_short"]
    shop.import_product(old)
    assert shop.saved() == ("<p>Długi opis</p>", "")

    assert shop.import_product(scraped_product()).counts["products"]["updated"] == 1
    assert shop.saved() == ("<p>Długi opis</p>", "<p>Krótki opis</p>")
    assert shop.import_product(scraped_product()).counts["products"]["unchanged"] == 1


def test_a_product_with_only_a_short_description_shows_it_once():
    # The source had no long description, so the scraper copied the short one into it (ADR 0007)
    shop = Catalogue()
    shop.import_product(scraped_product(description="<p>Krótki opis</p>"))
    assert shop.saved() == ("", "<p>Krótki opis</p>")
    assert shop.import_product(scraped_product(description="<p>Krótki opis</p>")).counts["products"]["unchanged"] == 1
