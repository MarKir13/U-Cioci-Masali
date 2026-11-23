"""The text of a manufacturer, from the scraped brand page: how it is built and imported (no shop needed)."""

import json

from fake_shop import FakeApi

from importer import data, mapping, steps
from importer.report import Report

HIMALAYA = {
    "name": "Himalaya",
    "url": "https://www.magiczne-indie.pl/brand/3-himalaya",
    "title": "Himalaya Herbals – oryginalne suplementy i kosmetyki ajurwedyjskie",
    "description": (
        "<p>Szukasz sklepu z oryginalną Himalaya Herbals?</p>\n"
        '<p>Zobacz też kategorię <a href="https://www.magiczne-indie.pl/335-suplementy-himalaya">Suplementy</a>.</p>\n'
        "<h2>Czym jest Himalaya Herbals</h2>\n<p>Marka z Indii.</p>"
    ),
    "faq_title": "Najczęstsze pytania o Himalaya",
    "faq": [
        {"question": "Czy Himalaya to lek?", "answer": "<p>Nie, to suplementy diety &amp; kosmetyki.</p>"},
        {"question": "Na co jest Himalaya?", "answer": "<p>Zależy od produktu.</p>"},
    ],
    "meta_title": "Himalaya Herbals – sklep online | Magiczne Indie",
    "meta_description": "Oryginalne Himalaya Herbals z Indii.",
}
DREAMS = {"name": "Himalaya's Dreams", "url": "https://www.magiczne-indie.pl/brand/199-himalaya-s-dreams"}
NO_PAGE = {"name": "Inne"}

PRODUCTS = [{"id": i, "brand": brand} for i, brand in enumerate(["Himalaya", "Himalaya's Dreams", "Inne"], 1)]
# Source category 335 was imported as shop category 77
LINKS = {335: "/77-suplementy-himalaya"}


# --- Text of a manufacturer ---


def test_a_link_to_a_source_category_points_to_our_shop():
    html = '<p><a href="https://www.magiczne-indie.pl/335-suplementy-himalaya">Suplementy</a></p>'
    assert mapping.relink_brand_html(html, LINKS) == '<p><a href="/77-suplementy-himalaya">Suplementy</a></p>'


def test_a_link_to_a_category_that_is_not_in_the_shop_is_dropped():
    html = '<a href="https://www.magiczne-indie.pl/999-gdzies">Gdzieś</a>'
    assert mapping.relink_brand_html(html, LINKS) == "Gdzieś"


def test_other_links_to_the_source_are_dropped_and_other_sites_are_kept():
    html = (
        '<a href="https://www.magiczne-indie.pl/brand/4-dabur">Dabur</a> '
        '<a href="https://example.org/a?b=1&amp;c=2">Inny</a>'
    )
    assert mapping.relink_brand_html(html, LINKS) == 'Dabur <a href="https://example.org/a?b=1&amp;c=2">Inny</a>'


def test_the_faq_follows_the_text_as_headings_and_answers():
    html = mapping.brand_description(HIMALAYA, LINKS)
    assert html.startswith("<p>Szukasz sklepu")
    assert '<a href="/77-suplementy-himalaya">Suplementy</a>' in html
    assert "magiczne-indie.pl" not in html
    assert html.endswith(
        "<h2>Najczęstsze pytania o Himalaya</h2>\n"
        "<h3>Czy Himalaya to lek?</h3>\n<p>Nie, to suplementy diety &amp; kosmetyki.</p>\n"
        "<h3>Na co jest Himalaya?</h3>\n<p>Zależy od produktu.</p>"
    )


def test_a_brand_without_text_has_no_description_and_no_faq():
    assert mapping.brand_description(NO_PAGE, LINKS) == ""
    assert mapping.brand_short_description(NO_PAGE) == ""


def test_the_short_description_is_the_first_paragraph_as_plain_text():
    assert mapping.brand_short_description(HIMALAYA) == "Szukasz sklepu z oryginalną Himalaya Herbals?"


def test_a_long_first_paragraph_is_cut_at_a_word():
    brand = {"description": "<p>" + "słowo " * 200 + "</p>"}
    short = mapping.brand_short_description(brand)
    assert len(short) <= mapping.SHORT_DESCRIPTION_MAX + 1
    assert short.endswith("słowo…")


def test_meta_fields_are_cut_to_the_limit_without_tags():
    assert mapping.limited(" Tytuł <b>marki</b> ", 255) == "Tytuł marki"
    cut = mapping.limited("słowo " * 200, mapping.META_TITLE_MAX)
    assert len(cut) <= mapping.META_TITLE_MAX
    assert cut.endswith("…")
    assert mapping.limited(None, 255) == ""


# --- Import on the fake shop ---


def run_import(api: FakeApi, brands: list[dict]) -> Report:
    report = Report()
    api.writes.clear()
    shop = steps.read_shop(api)
    steps.import_manufacturers(api, shop, PRODUCTS, report, brands, LINKS)
    return report


def saved(api: FakeApi) -> dict[str, dict]:
    return {m["name"]: m for m in api.all("manufacturers")}


def test_the_brand_page_is_written_to_the_manufacturer():
    api = FakeApi()
    report = run_import(api, [HIMALAYA, DREAMS, NO_PAGE])
    assert report.counts["manufacturers"]["created"] == 3

    himalaya = saved(api)["Himalaya"]
    assert himalaya["description"] == mapping.brand_description(HIMALAYA, LINKS)
    assert himalaya["short_description"] == "Szukasz sklepu z oryginalną Himalaya Herbals?"
    # The page's H1, which the theme prints as the heading, and not the source's <title> (ADR 0014)
    assert himalaya["meta_title"] == HIMALAYA["title"]
    assert himalaya["meta_title"] != HIMALAYA["meta_title"]
    assert himalaya["meta_description"] == "Oryginalne Himalaya Herbals z Indii."


def test_read_shop_keeps_the_text_of_a_manufacturer():
    # PUT replaces the whole record, so the shop is read with its text: with only id and name every run would
    # see empty texts and write all the brands again
    api = FakeApi()
    run_import(api, [HIMALAYA])
    manufacturer = steps.read_shop(api).manufacturers["Himalaya"]
    assert manufacturer["description"] == mapping.brand_description(HIMALAYA, LINKS)
    assert manufacturer["meta_title"] == HIMALAYA["title"]


def test_the_fake_shop_returns_only_the_fields_that_display_asks_for():
    api = FakeApi()
    run_import(api, [HIMALAYA])
    assert set(api.list("manufacturers", display="[id,name]")[0]) == {"id", "name"}
    assert "description" in api.list("manufacturers")[0]


def test_a_brand_with_a_similar_name_is_not_merged():
    api = FakeApi()
    run_import(api, [HIMALAYA, DREAMS, NO_PAGE])
    manufacturers = saved(api)
    assert len(manufacturers) == 3
    assert manufacturers["Himalaya's Dreams"]["description"] == ""
    assert manufacturers["Himalaya's Dreams"]["id"] != manufacturers["Himalaya"]["id"]


def test_a_brand_without_a_page_keeps_its_name_only():
    api = FakeApi()
    run_import(api, [HIMALAYA, DREAMS, NO_PAGE])
    inne = saved(api)["Inne"]
    assert (inne["description"], inne["short_description"], inne["meta_title"]) == ("", "", "")


def test_a_second_run_changes_nothing():
    api = FakeApi()
    run_import(api, [HIMALAYA, DREAMS, NO_PAGE])
    report = run_import(api, [HIMALAYA, DREAMS, NO_PAGE])
    assert report.counts["manufacturers"]["unchanged"] == 3
    assert report.counts["manufacturers"]["created"] == 0
    assert api.writes == []
    assert len(api.all("manufacturers")) == 3


def test_a_changed_page_updates_the_manufacturer_once():
    api = FakeApi()
    run_import(api, [HIMALAYA, DREAMS, NO_PAGE])
    changed = {**HIMALAYA, "faq": HIMALAYA["faq"][:1]}

    report = run_import(api, [changed, DREAMS, NO_PAGE])
    assert report.counts["manufacturers"]["updated"] == 1
    assert report.counts["manufacturers"]["created"] == 0
    assert "Na co jest Himalaya?" not in saved(api)["Himalaya"]["description"]
    assert run_import(api, [changed, DREAMS, NO_PAGE]).counts["manufacturers"]["unchanged"] == 3


def test_a_page_added_later_updates_a_manufacturer_that_had_only_its_name():
    # A shop imported before brands.json existed
    api = FakeApi()
    run_import(api, [])
    assert saved(api)["Himalaya"]["description"] == ""

    report = run_import(api, [HIMALAYA])
    assert report.counts["manufacturers"]["updated"] == 1
    assert saved(api)["Himalaya"]["description"] != ""


def test_brand_matching_ignores_case():
    api = FakeApi()
    run_import(api, [{**HIMALAYA, "name": "HIMALAYA"}])
    assert saved(api)["Himalaya"]["short_description"] == "Szukasz sklepu z oryginalną Himalaya Herbals?"


# --- Reading brands.json ---

SCHEMA = {
    "$defs": {
        "Brand": {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1}, "description": {"type": ["string", "null"]}},
            "required": ["name"],
            "additionalProperties": False,
        }
    }
}


def test_invalid_brand_records_are_rejected_with_a_reason(tmp_path):
    (tmp_path / "brands.json").write_text(
        json.dumps([{"name": "Dabur"}, {"name": "Vicco", "description": 5}], ensure_ascii=False), encoding="utf-8"
    )
    valid, rejected = data.load_brands(tmp_path, SCHEMA)
    assert [b["name"] for b in valid] == ["Dabur"]
    assert [name for name, _ in rejected] == ["Vicco"]


def test_results_without_brands_json_give_no_brands(tmp_path):
    assert data.load_brands(tmp_path, SCHEMA) == ([], [])
    (tmp_path / "brands.json").write_text("[]", encoding="utf-8")
    assert data.load_brands(tmp_path, {"$defs": {}}) == ([], [])
