"""The conversion rules of importer/mapping.py, on hand-picked cases and on the real scraped data."""

import json
from collections import Counter
from pathlib import Path

import pytest

from importer import mapping

RESULTS = Path(__file__).resolve().parents[3] / "scraper-results"


def real_products() -> list[dict]:
    path = RESULTS / "products.jsonl"
    if not path.is_file():
        pytest.skip("scraper-results/products.jsonl not found")
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


# --- Prices ---


@pytest.mark.parametrize(
    ("gross", "vat", "net"),
    [
        ("14.49", 23.0, "11.780488"),
        ("23.20", 8.0, "21.481481"),
        ("10.50", 5.0, "10.000000"),
        ("1490.00", 23.0, "1211.382114"),
    ],
)
def test_net_price(gross, vat, net):
    assert mapping.net_price(gross, vat) == net


def test_every_real_price_comes_back_to_the_grosz():
    """The shop shows net x (1 + VAT) rounded to the grosz: it must equal the source price for every product."""
    for product in real_products():
        for gross in (product["regular_price"], product["price"]):
            net = mapping.net_price(gross, product["vat_rate"])
            assert mapping.gross_price(net, product["vat_rate"]) == f"{float(gross):.2f}", product["id"]


def test_promotion_amount():
    assert mapping.promotion_amount("23.94", "21.07") == "2.87"
    assert mapping.promotion_amount("10", "10") == "0.00"


# --- Weight (the cases from ADR 0008) ---


@pytest.mark.parametrize(
    ("value", "kg"),
    [
        ("0.011", 0.011),  # bracelet: below 1, as grams it would weigh less than a paperclip
        ("0.040000", 0.04),  # 10 ml scented oil in its box
        ("1.0", 0.001),  # foil gloves: a whole number is grams
        ("1.187", 1.187),  # Buddha lava lamp: decimals below 5 are kilograms
        ("1.3", 1.3),  # salt candle holder
        ("10.0", 0.01),
        ("74.000000", 0.074),
        ("1010.0", 1.01),
    ],
)
def test_weight_kg(value, kg):
    assert mapping.weight_kg({"value": value, "unit": "g"}) == pytest.approx(kg)


def test_no_weight_is_zero():
    assert mapping.weight_kg(None) == 0.0


def test_no_real_product_is_heavier_than_a_carrier_allows():
    weights = [mapping.weight_kg(p["weight"]) for p in real_products()]
    assert max(weights) < 50


# --- Stock ---


def test_stock_is_the_same_on_every_call():
    assert [mapping.stock_quantity(100) for _ in range(3)] == [mapping.stock_quantity(100)] * 3


def test_stock_of_product_100():
    # h = 12490511913535565397: last digit 7 (in stock), the digit before it 9, so 1 + 9
    assert mapping.stock_quantity(100) == 10


def test_real_stock_is_0_to_10_with_5_to_20_percent_at_0():
    counts = Counter(mapping.stock_quantity(p["id"]) for p in real_products())
    assert set(counts) <= set(range(0, 11))
    share_out = counts[0] / sum(counts.values())
    assert 0.05 <= share_out <= 0.20


# --- Barcodes ---


@pytest.mark.parametrize(
    ("ean", "expected"),
    [
        ("8901138515010", ("8901138515010", "")),  # EAN-13
        ("96385074", ("96385074", "")),  # EAN-8
        ("036000291452", ("", "036000291452")),  # UPC-A
        ("8901138515011", ("", "")),  # wrong check digit
        ("12345", ("", "")),
        (None, ("", "")),
        ("", ("", "")),
    ],
)
def test_barcodes(ean, expected):
    assert mapping.barcodes(ean) == expected


# --- Link rewrite ---


def test_link_rewrite_from_category_and_product_urls():
    assert mapping.link_rewrite("https://www.magiczne-indie.pl/38-kosmetyki-do-wlosow", "x") == "kosmetyki-do-wlosow"
    url = "https://www.magiczne-indie.pl/100-kredka-do-oczu-naturalna-kajal-himalaya-27g.html"
    assert mapping.link_rewrite(url, "x") == "kredka-do-oczu-naturalna-kajal-himalaya-27g"


def test_link_rewrite_falls_back_to_the_name_in_ascii():
    assert mapping.link_rewrite("https://example.com/12-ąę!", "Żywność i Przyprawy") == "zywnosc-i-przyprawy"


def test_every_real_slug_is_valid():
    for product in real_products():
        assert mapping.LINK_REWRITE.match(mapping.link_rewrite(product["url"], product["name"])), product["id"]


# --- Descriptions ---


def test_visible_text_ignores_what_prestashop_changes_on_save():
    source = (
        '<p><a href="x" rel="pmsil">Himalaya</a> kredka &amp; puder<br>czarna</p>'
        + '<img src="data:image/png;base64,A">'
    )
    saved = '<p><a href="x">Himalaya</a> kredka &amp; puder<br />czarna</p>'
    assert mapping.visible_text(source) == mapping.visible_text(saved) == "Himalayakredka&puderczarna"


def test_visible_text_ignores_a_removed_empty_tag():
    # Found on 14 real products: the cleaner drops the empty <span> between "W" and "."
    assert mapping.visible_text("ezoteryki W<span></span>. Reich") == mapping.visible_text("ezoteryki W. Reich")


def test_visible_text_sees_a_changed_word():
    assert mapping.visible_text("<p>stara cena</p>") != mapping.visible_text("<p>nowa cena</p>")


# The two ways the source writes a video player (products 7219 and 7229)
VIDEO_LF = (
    '<video controls="controls" height="400" width="400">\n<source src="/img/cms/a.mp4" type="video/mp4"/>\n</video>'
)
VIDEO_CRLF = (
    '<video width="400" height="400" controls="controls">\r\n'
    '<source src="/img/cms/b.mp4" type="video/mp4" />\r\n</video>'
)


@pytest.mark.parametrize("video", [VIDEO_LF, VIDEO_CRLF])
def test_without_videos_removes_the_player_and_keeps_the_text(video):
    html = f"<p>Rozmiar 12 cm</p>\n<p>{video}</p>\n<p>*podstawka nie stanowi</p>"
    assert mapping.without_videos(html) == "<p>Rozmiar 12 cm</p>\n<p></p>\n<p>*podstawka nie stanowi</p>"


def test_without_videos_removes_two_players_and_what_is_between_them_stays():
    # Product 8082 has two players in a row
    html = f"<strong>Waga 1750 g.</strong>{VIDEO_CRLF}<br />{VIDEO_LF}<p>koniec</p>"
    assert mapping.without_videos(html) == "<strong>Waga 1750 g.</strong><br /><p>koniec</p>"


def test_without_source_links_keeps_the_text_and_drops_the_address():
    link = '<a href="https://www.magiczne-indie.pl/399-miedziane-naczynia-do-wody">Miedziane naczynia</a>'
    html = f"<p>Wróć do {link}.</p>"
    assert mapping.without_source_links(html) == "<p>Wróć do Miedziane naczynia.</p>"


def test_without_source_links_handles_other_attributes_and_letter_case():
    source = "<A class=\"x\" HREF='http://magiczne-indie.pl/content/54-a' title=\"t\">jak <b>czyścić</b></A>"
    html = f'{source} i <a href="/koszyk">koszyk</a>'
    assert mapping.without_source_links(html) == 'jak <b>czyścić</b> i <a href="/koszyk">koszyk</a>'


def test_without_source_links_leaves_other_sites_alone():
    html = '<a href="http://www.lawana.pl/x">Lawana</a>'
    assert mapping.without_source_links(html) == html


def test_no_category_description_links_to_the_source_shop_after_the_import_mapping():
    path = RESULTS / "categories.json"
    if not path.is_file():
        pytest.skip("scraper-results/categories.json not found")
    for category in json.loads(path.read_text(encoding="utf-8")):
        assert not mapping.SOURCE_LINK.search(mapping.without_source_links(category.get("description") or ""))


def test_without_videos_ignores_letter_case():
    assert mapping.without_videos('<p>a<VIDEO controls><SOURCE src="/x.mp4"></Video>b</p>') == "<p>ab</p>"


def test_without_videos_leaves_a_description_without_a_player_as_it_was():
    html = '<p><a href="https://www.magiczne-indie.pl/x.html">Himalaya</a> <img src="https://www.magiczne-indie.pl/img/cms/1.jpg"></p>'
    assert mapping.without_videos(html) == html


def test_no_real_description_keeps_a_video_or_loses_text():
    with_video = 0
    for product in real_products():
        description = product["description"]
        cleaned = mapping.without_videos(description)
        with_video += cleaned != description
        assert "<video" not in cleaned.lower() and "</video" not in cleaned.lower(), product["id"]
        assert mapping.visible_text(cleaned) == mapping.visible_text(description), product["id"]
    # The 7 singing bowls of the issue; a new scrape with more videos shows up here
    assert with_video == 7


# --- Category tree ---

CATEGORIES = [
    {"id": 3, "parent_id": 2},
    {"id": 2, "parent_id": 1},
    {"id": 1, "parent_id": None},
    {"id": 4, "parent_id": None},
]


def test_parents_come_before_children():
    order = [c["id"] for c in mapping.parents_first(CATEGORIES)]
    assert order.index(1) < order.index(2) < order.index(3)


def test_with_descendants():
    assert mapping.with_descendants({1}, CATEGORIES) == {1, 2, 3}
    assert mapping.with_descendants({4}, CATEGORIES) == {4}
