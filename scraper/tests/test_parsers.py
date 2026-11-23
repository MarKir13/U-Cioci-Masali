"""Tests of the parsers on pages saved from the source shop. They do not use the network."""

import html as html_lib
import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from scraper.models import Category
from scraper.parsers import (
    backfill_values,
    children_by_parent,
    missing_parents,
    next_page_url,
    parse_brand,
    parse_brand_index,
    parse_category,
    parse_product,
    parse_sitemap,
    parse_sitemap_index,
    product_urls,
    promo_end_from,
    round_price,
)

FIXTURES = Path(__file__).parent / "fixtures"

CATEGORY_URL = "https://www.magiczne-indie.pl/104-olejki-do-wlosow"
HOME_URL = "https://www.magiczne-indie.pl/"
PRODUCT_URL = "https://www.magiczne-indie.pl/1028-ajurwedyjski-olejek-lagodzacy-bol-miesni-i-stawow-for-muscle-joint-pain-ayush-200ml.html"

# Minimal pages for the error cases: each test leaves out one of these parts.
H1 = '<h1 class="page-title-section">Olejki do włosów</h1>'
BREADCRUMB = """
<script type="application/ld+json">
{"@type": "BreadcrumbList", "itemListElement": [
  {"position": 1, "name": "Strona główna", "item": "https://www.magiczne-indie.pl/"},
  {"position": 2, "name": "Olejki do włosów", "item": "https://www.magiczne-indie.pl/104-olejki-do-wlosow"}
]}
</script>
"""


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_top_level_category_has_no_parent():
    """/8-kosmetyki lies directly under the home page, so it has no parent."""
    category = parse_category(
        "https://www.magiczne-indie.pl/8-kosmetyki",
        read_fixture("category_with_subcategories.html"),
    )
    assert category.id == 8
    assert category.name == "Kosmetyki"
    assert category.parent_id is None


def test_category_has_its_description():
    """The text under the category name is kept as HTML, with the Polish characters intact."""
    category = parse_category(
        "https://www.magiczne-indie.pl/8-kosmetyki",
        read_fixture("category_with_subcategories.html"),
    )
    assert category.description.startswith("<p>Tylko u nas kupisz naturalne henny do farbowania włosów")
    assert category.description.endswith("naturalnym pięknem i blaskiem.</p>")


def test_category_without_a_description_has_none():
    """A page with no div#category-description is not an error: many categories have no text."""
    assert parse_category(CATEGORY_URL, H1 + BREADCRUMB).description is None


def test_blank_description_is_none():
    """An empty or whitespace-only description div means the same as no div."""
    page = H1 + BREADCRUMB + '<div id="category-description" class="category__description">  </div>'
    assert parse_category(CATEGORY_URL, page).description is None


def test_category_has_a_parent():
    """The parent is the second-to-last breadcrumb item, and Polish characters in the name stay intact."""
    category = parse_category(
        "https://www.magiczne-indie.pl/104-olejki-do-wlosow",
        read_fixture("category_leaf_first_page.html"),
    )
    assert category.id == 104
    assert category.name == "Olejki do włosów"
    assert category.parent_id == 38


def test_minimal_page_is_parsed():
    """Checks that the error cases below fail only because of the part they leave out."""
    category = parse_category(CATEGORY_URL, H1 + BREADCRUMB)
    assert category.id == 104
    assert category.parent_id is None


def test_page_without_name_is_rejected():
    with pytest.raises(ValueError, match="No category name"):
        parse_category(CATEGORY_URL, BREADCRUMB)


def test_page_without_breadcrumb_is_rejected_with_its_url():
    with pytest.raises(ValueError, match="104-olejki-do-wlosow: No BreadcrumbList"):
        parse_category(CATEGORY_URL, H1)


def test_home_page_is_not_a_category():
    with pytest.raises(ValueError, match="Id can't be extracted"):
        parse_category(HOME_URL, H1 + BREADCRUMB)


def test_error_names_the_parent_url_that_is_not_a_category():
    bad_parent = BREADCRUMB.replace(f'"{HOME_URL}"', '"https://www.magiczne-indie.pl/content/4-regulamin"')
    with pytest.raises(ValueError, match="content/4-regulamin"):
        parse_category(CATEGORY_URL, H1 + bad_parent)


def test_breadcrumb_without_parent_is_rejected():
    only_this_page = BREADCRUMB.replace(
        '{"position": 1, "name": "Strona główna", "item": "https://www.magiczne-indie.pl/"},\n',
        "",
    )
    with pytest.raises(ValueError, match="fewer than 2 items"):
        parse_category(CATEGORY_URL, H1 + only_this_page)


def make_category(category_id: int, parent_id: int | None) -> Category:
    """A category with a made-up name and URL, for tests where only the ids matter."""
    return Category(
        id=category_id,
        name=f"Category {category_id}",
        url=f"https://www.magiczne-indie.pl/{category_id}-category",
        parent_id=parent_id,
    )


def ids(categories: list[Category]) -> list[int]:
    return [category.id for category in categories]


def test_children_are_grouped_by_parent_id():
    """Top-level categories are under None, the rest under their parent, in the original order."""
    tree = children_by_parent(
        [
            make_category(8, None),
            make_category(38, 8),
            make_category(104, 38),
            make_category(45, 8),
        ]
    )
    assert ids(tree[None]) == [8]
    assert ids(tree[8]) == [38, 45]
    assert ids(tree[38]) == [104]
    assert 104 not in tree  # a category without children gets no key


def test_empty_list_gives_empty_tree():
    assert children_by_parent([]) == {}


def test_category_with_unknown_parent_is_reported():
    categories = [make_category(8, None), make_category(104, 999)]
    assert ids(missing_parents(categories)) == [104]


def test_top_level_category_is_not_reported_as_missing():
    """parent_id None means the home page, not a parent that was not found."""
    assert missing_parents([make_category(8, None)]) == []


def test_complete_tree_has_no_missing_parents():
    categories = [make_category(8, None), make_category(38, 8), make_category(104, 38)]
    assert missing_parents(categories) == []


def test_parsed_pages_report_parent_that_was_not_parsed():
    """Olejki (104) has parent 38, which is not among the parsed pages, so it is reported."""
    categories = [
        parse_category(
            "https://www.magiczne-indie.pl/8-kosmetyki",
            read_fixture("category_with_subcategories.html"),
        ),
        parse_category(
            "https://www.magiczne-indie.pl/104-olejki-do-wlosow",
            read_fixture("category_leaf_first_page.html"),
        ),
    ]
    assert ids(missing_parents(categories)) == [104]


SHOP = "https://www.magiczne-indie.pl"

SAMPLE_PRODUCTS = [
    f"{SHOP}/242-olejek-amla-do-wlosow-ciemnych-200ml-dabur.html",
    f"{SHOP}/5425-bio-amalaki-60-kapsulek-suplement-diety-maharishi-ayurveda.html",
    f"{SHOP}/9842-lampa-budda-efekt-stopionej-lawy-owalna-podstawa.html",
]
SAMPLE_CATEGORIES = [
    f"{SHOP}/8-kosmetyki",
    f"{SHOP}/38-kosmetyki-do-wlosow",
    f"{SHOP}/104-olejki-do-wlosow",
]
BRAND_PAGE = f"{SHOP}/brand/24-auromere"
SAMPLE_OTHER_PAGES = [
    f"{SHOP}/",
    f"{SHOP}/nie-znaleziono-strony",
    f"{SHOP}/?controller=module-ps_shoppingcart-ajax",
    f"{SHOP}/content/1-koszt-wysylki-i-czas-dostawy",
    BRAND_PAGE,
]


def parse_sample_sitemap() -> tuple[list[str], list[str]]:
    return parse_sitemap(read_fixture("sitemap_sample.xml"))


def test_sitemap_index_lists_the_sitemap():
    assert parse_sitemap_index(read_fixture("sitemap_index.xml")) == [f"{SHOP}/1_pl_0_sitemap.xml"]


def test_sitemap_gives_products_and_categories_in_order():
    """The sample has 3 products and 3 categories, listed in the order of the sitemap."""
    products, categories = parse_sample_sitemap()
    assert products == SAMPLE_PRODUCTS
    assert categories == SAMPLE_CATEGORIES


def test_sitemap_skips_other_pages():
    """Home, CMS, module and brand pages are neither products nor categories."""
    products, categories = parse_sample_sitemap()
    for url in SAMPLE_OTHER_PAGES:
        assert url not in products
        assert url not in categories


def test_brand_page_is_not_a_category():
    """/brand/{id}-{slug} ends like a category, but brands are not part of the category tree."""
    _, categories = parse_sample_sitemap()
    assert BRAND_PAGE not in categories


def test_product_is_not_taken_for_a_category():
    _, categories = parse_sample_sitemap()
    assert not any(url.endswith(".html") for url in categories)


def test_image_addresses_are_skipped():
    """Products have <image:loc> entries in another namespace, which are not pages."""
    products, categories = parse_sample_sitemap()
    assert not any(url.endswith(".jpg") for url in products + categories)


def test_cdata_is_removed_from_addresses():
    """<loc> wraps the address in CDATA, and ElementTree strips it by itself."""
    products, categories = parse_sample_sitemap()
    assert all(url.startswith("https://") for url in products + categories)


def test_first_page_gives_12_products_and_next_page():
    """Ensure the first page yields exactly 12 unique, absolute product URLs and a link to page 2."""
    url = "https://www.magiczne-indie.pl/104-olejki-do-wlosow"
    html = read_fixture("category_leaf_first_page.html")

    products = product_urls(url, html)
    assert len(products) == 12
    assert len(set(products)) == 12
    for product_url in products:
        assert product_url.startswith("https://www.magiczne-indie.pl/")

    next_page = next_page_url(url, html)
    assert next_page == "https://www.magiczne-indie.pl/104-olejki-do-wlosow?page=2"


def test_middle_page_gives_products_and_next_page():
    """Ensure a middle page yields unique, absolute product URLs and a link to the next page."""
    url = "https://www.magiczne-indie.pl/104-olejki-do-wlosow?page=3"
    html = read_fixture("category_leaf_middle_page.html")

    products = product_urls(url, html)
    assert len(products) == 12
    assert len(set(products)) == 12
    for product_url in products:
        assert product_url.startswith("https://www.magiczne-indie.pl/")

    next_page = next_page_url(url, html)
    assert next_page == "https://www.magiczne-indie.pl/104-olejki-do-wlosow?page=4"


def test_last_page_gives_10_products_and_no_next_page():
    """Ensure the last page yields exactly 10 unique, absolute product URLs and returns None for the next page."""
    url = "https://www.magiczne-indie.pl/104-olejki-do-wlosow?page=8"
    html = read_fixture("category_leaf_last_page.html")

    products = product_urls(url, html)
    assert len(products) == 10
    assert len(set(products)) == 10
    for product_url in products:
        assert product_url.startswith("https://www.magiczne-indie.pl/")

    next_page = next_page_url(url, html)
    assert next_page is None


def test_parse_product_with_one_image():
    """Verify single image extraction, basic attributes and JSON data source."""
    html = read_fixture("product_one_image.html")
    product = parse_product(PRODUCT_URL, html)

    assert product is not None
    assert product.id == 1028
    assert product.name == "Ajurwedyjski Olejek Łagodzący Ból Mięśni i Stawów (For Muscle & Joint Pain) Ayush 200ml"
    assert product.brand == "AYUSH"
    assert product.ean == "8906086960004"
    assert float(product.price) == 54.99
    assert float(product.regular_price) == 54.99
    assert product.has_discount is False
    assert product.vat_rate == 23.0

    assert product.weight is not None
    assert product.weight.value == "100.000000"
    assert product.weight.unit == "g"

    assert len(product.images) == 1
    assert (
        str(product.images[0].source_url)
        == "https://www.magiczne-indie.pl/5290-product_main_2x/ajurwedyjski-olejek-lagodzacy-bol-miesni-i-stawow-for-muscle-joint-pain-ayush-200ml.jpg"
    )

    assert product.category_ids == [179, 8, 37]


def test_missing_data_product_raises_error():
    html_without_data = '<div class="js-product-details">No data here</div>'
    with pytest.raises(ValueError, match=r"Missing data-product attribute.*at https://"):
        parse_product(PRODUCT_URL, html_without_data)


def test_invalid_json_in_data_product_raises_error():
    with pytest.raises(ValueError, match=r"Invalid JSON in data-product.*at https://"):
        parse_product(PRODUCT_URL, '<div class="js-product-details" data-product="invalid"></div>')


def test_parse_product_discounted():
    """Test parsing a discounted product based on acceptance criteria."""
    html = read_fixture("product_discounted.html")
    product = parse_product("https://www.magiczne-indie.pl/test-discount.html", html)

    assert product is not None
    assert product.has_discount is True
    assert float(product.price) == 64.72
    assert float(product.regular_price) == 69.59
    assert product.vat_rate == 8.0

    assert product.category_ids == [385, 80, 55]
    assert product.weight is None
    assert product.size is None
    assert product.color is None
    assert product.material is None
    assert product.pattern is None


def test_parse_product_many_images():
    """Test parsing a product with multiple images."""
    html = read_fixture("product_many_images.html")
    product = parse_product("https://www.magiczne-indie.pl/test-images.html", html)

    assert product is not None
    assert product.has_discount is False
    assert len(product.images) == 10
    assert product.category_ids == [393, 232]


def test_parse_product_with_family():
    """Test parsing a product with variants (family) and specific JSON-LD attributes."""
    html = read_fixture("product_with_family.html")
    product = parse_product("https://www.magiczne-indie.pl/test-family.html", html)

    assert product is not None
    assert product.size == "200 ml"
    assert product.pattern == "Amla"
    assert product.weight is not None
    assert product.weight.value == "250.000000"
    assert len(product.family) >= 1
    assert product.category_ids == [104, 8, 38]


def product_html(weight: dict | None = None, **data_overrides) -> str:
    """A minimal product page: data-product plus, with `weight`, a JSON-LD Product block."""
    data = {
        "id": 7,
        "name": "Olejek",
        "description": "<p>Opis</p>",
        "price_amount": 10,
        "price_without_reduction": 10,
        "has_discount": False,
        "rate": 23,
        "id_category_default": 5,
        "images": [{"bySize": {"product_main_2x": {"url": "https://www.magiczne-indie.pl/1-product_main_2x/x.jpg"}}}],
        **data_overrides,
    }
    page = f"<div class=\"js-product-details\" data-product='{html_lib.escape(json.dumps(data))}'></div>"
    if weight is not None:
        ld = {"@type": "Product", "weight": weight}
        page += f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    return page


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (2.675, "2.68"),  # round(2.675, 2) gives 2.67
        (1.005, "1.01"),  # round(1.005, 2) gives 1.0
        (69.58764, "69.59"),
        (272.989999, "272.99"),
        (17.2, "17.20"),
        (10, "10.00"),
        ("64.72", "64.72"),
        (0.125, "0.13"),
    ],
)
def test_round_price_rounds_halves_up(raw, expected):
    assert round_price(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", [None, True, "abc", "", float("nan"), float("inf"), "1e100"])
def test_round_price_leaves_anything_else_for_validation(raw):
    result = round_price(raw)
    assert result is raw or (result != result and raw != raw)  # nan is not equal to itself


def test_price_rounded_up_by_the_shop_is_not_above_the_regular_price():
    """The shop shows 2.68 for 2.675. Rounding both prices the same way keeps price <= regular_price."""
    product = parse_product(PRODUCT_URL, product_html(price_amount=2.68, price_without_reduction=2.675))
    assert product is not None
    assert product.price == Decimal("2.68")
    assert product.regular_price == Decimal("2.68")


def test_unrounded_current_price_is_rounded_too():
    product = parse_product(PRODUCT_URL, product_html(price_amount=64.72001, price_without_reduction=69.58764))
    assert product is not None
    assert (product.price, product.regular_price) == (Decimal("64.72"), Decimal("69.59"))


def test_missing_prices_are_rejected_and_logged(caplog):
    with caplog.at_level(logging.ERROR):
        assert parse_product(PRODUCT_URL, product_html(price_without_reduction=None)) is None
    assert f"Invalid Product at {PRODUCT_URL}" in caplog.text


def test_weight_without_unit_is_skipped_but_the_product_is_kept(caplog):
    with caplog.at_level(logging.WARNING):
        product = parse_product(PRODUCT_URL, product_html(weight={"value": "250.000000"}))
    assert product is not None
    assert product.weight is None
    assert f"Weight '250.000000' has no unit, skipped: {PRODUCT_URL}" in caplog.text


@pytest.mark.parametrize("unit", ["", "   ", None, 5])
def test_weight_with_empty_or_odd_unit_is_skipped(unit):
    product = parse_product(PRODUCT_URL, product_html(weight={"value": "250.000000", "unitCode": unit}))
    assert product is not None
    assert product.weight is None


def test_weight_with_unit_is_kept():
    product = parse_product(PRODUCT_URL, product_html(weight={"value": "250.000000", "unitCode": "g"}))
    assert product is not None
    assert (product.weight.value, product.weight.unit) == ("250.000000", "g")


@pytest.mark.parametrize("weight", [{}, {"value": ""}, {"value": None, "unitCode": "g"}, "250 g", []])
def test_missing_or_odd_weight_gives_none(weight):
    product = parse_product(PRODUCT_URL, product_html(weight=weight))
    assert product is not None
    assert product.weight is None


def test_short_description_is_kept_next_to_the_long_one():
    """The fixture's short description is the text the source shows above the "Add to cart" button."""
    product = parse_product(PRODUCT_URL, read_fixture("product_one_image.html"))
    assert product.description_short == (
        "<p>W 100% naturalny olejek z cennymi wyciągami z ajurwedyjskich ziół. "
        "Polecany dla sportowców a także osób starszych.</p>"
    )
    assert product.description != product.description_short


@pytest.mark.parametrize("short", ["", "   ", "<p></p>", "<p>&nbsp;</p>\r\n<p></p>", None])
def test_short_description_without_text_is_null(short):
    product = parse_product(PRODUCT_URL, product_html(description_short=short))
    assert product is not None
    assert product.description_short is None


def test_page_without_short_description_gives_null():
    product = parse_product(PRODUCT_URL, product_html())
    assert product is not None
    assert product.description_short is None


def test_backfill_values_read_only_data_product():
    page = product_html(description_short="<p>Krótki</p>")
    assert backfill_values(PRODUCT_URL, page) == {"description_short": "<p>Krótki</p>", "promo_end": None}
    with pytest.raises(ValueError, match="Missing data-product"):
        backfill_values(PRODUCT_URL, "<div>no product</div>")


# ---------- The end of a promotion ----------


def test_promotion_end_of_a_discounted_product():
    """The saved page has a promotion that ends on 31.10.2026; the source's card shows it as "do 31.10.2026"."""
    product = parse_product("https://www.magiczne-indie.pl/test-discount.html", read_fixture("product_discounted.html"))
    assert product.promo_end == datetime(2026, 10, 31, 23, 59)
    assert product.model_dump(mode="json")["promo_end"] == "2026-10-31T23:59:00"


def test_product_without_a_discount_has_no_promotion_end():
    """priceValidUntil of the JSON-LD block is on this page too, but it is not the end of a promotion."""
    product = parse_product(PRODUCT_URL, read_fixture("product_one_image.html"))
    assert product.has_discount is False
    assert product.promo_end is None


@pytest.mark.parametrize(
    "data",
    [
        {"has_discount": True, "specific_prices": {"to": "0000-00-00 00:00:00"}},  # a promotion without an end
        {"has_discount": True, "specific_prices": {"to": ""}},
        {"has_discount": True, "specific_prices": False},  # PrestaShop sends false when there is none
        {"has_discount": True},
        {"has_discount": False, "specific_prices": {"to": "2026-11-14 23:59:00"}},  # e.g. a quantity discount
    ],
)
def test_no_promotion_end(data):
    assert promo_end_from(data) is None


def test_invalid_promotion_end_rejects_the_product():
    problems = []
    page = product_html(price_amount=8, has_discount=True, specific_prices={"to": "14.11.2026"})
    assert parse_product(PRODUCT_URL, page, problems) is None
    assert "promo_end" in problems[0]


# ---------- Brand pages ----------

BRAND_URL = "https://www.magiczne-indie.pl/brand/3-himalaya"


def himalaya():
    return parse_brand("Himalaya", BRAND_URL, read_fixture("brand_with_seo_faq.html"))


def test_brand_page_has_its_title_and_meta_tags():
    brand = himalaya()
    assert brand.name == "Himalaya"
    assert str(brand.url) == BRAND_URL
    assert brand.title == "Himalaya Herbals – oryginalne suplementy i kosmetyki ajurwedyjskie"
    assert brand.meta_title == "Himalaya Herbals – sklep online | Suplementy i kosmetyki | Magiczne Indie"
    assert brand.meta_description.startswith("Oryginalne Himalaya Herbals z Indii – suplementy, pasty, kremy.")
    assert "\n" not in brand.meta_description


def test_brand_description_has_the_intro_and_the_sections():
    description = himalaya().description
    # The intro comes first, with its two paragraphs
    assert description.startswith("<p>Szukasz sklepu z oryginalną Himalaya Herbals?")
    assert description.count("<h2>") == 4
    headings = [line for line in description.splitlines() if line.startswith("<h2>")]
    assert headings == [
        "<h2>Czym jest Himalaya Herbals</h2>",
        "<h2>Suplementy Himalaya</h2>",
        "<h2>Kosmetyki Himalaya</h2>",
        "<h2>Dlaczego Himalaya w Magicznych Indiach</h2>",
    ]


def test_brand_description_keeps_lists_bold_text_and_the_category_link():
    description = himalaya().description
    assert description.count("<ul>") == 3
    assert description.count("<li>") == 13
    assert "<li><strong>Mentat</strong> — klasyczna formuła" in description
    assert (
        '<a href="https://www.magiczne-indie.pl/335-suplementy-himalaya-herbals-himalaya-herbs">'
        "Suplementy Himalaya Herbals</a>"
    ) in description


def test_brand_description_has_neither_the_faq_nor_page_widgets():
    description = himalaya().description
    assert "Najczęstsze pytania" not in description
    assert "accordion" not in description
    assert "Czytaj więcej" not in description
    assert "<button" not in description


def test_brand_faq_has_four_questions_with_answers():
    brand = himalaya()
    assert brand.faq_title == "Najczęstsze pytania o Himalaya"
    assert [item.question for item in brand.faq] == [
        "Na co jest Himalaya?",
        "Czy Himalaya to lek?",
        "Jaki jest skład produktów Himalaya?",
        "Mentat Himalaya — jak dawkować?",
    ]
    assert brand.faq[1].answer.startswith("<p>Większość produktów Himalaya dostępnych w sklepie")
    assert all(item.answer.startswith("<p>") and item.answer.endswith("</p>") for item in brand.faq)


def test_brand_html_has_no_scripts_styles_or_event_handlers():
    brand = himalaya()
    html = brand.description + "".join(item.answer for item in brand.faq)
    assert not re.search(r"<\s*(script|style)", html, re.IGNORECASE)
    assert not re.search(r"\son[a-z]+\s*=", html, re.IGNORECASE)


def test_brand_page_with_only_a_paragraph_has_a_description_and_no_faq():
    brand = parse_brand(
        "Dabur", "https://www.magiczne-indie.pl/brand/4-dabur", read_fixture("brand_with_description_only.html")
    )
    assert brand.title == "Dabur"
    assert brand.description.startswith("<p>W naszej ofercie znajdziesz naturalne produkty Dabur.")
    assert brand.faq == []
    assert brand.faq_title is None
    assert brand.meta_description is None  # the source's tag is empty


def test_brand_page_without_a_description():
    brand = parse_brand(
        "Vicco", "https://www.magiczne-indie.pl/brand/5-vicco", read_fixture("brand_without_description.html")
    )
    assert brand.title == "Vicco"
    assert brand.description is None
    assert brand.faq == []
    assert brand.meta_title == "Vicco"


def test_brand_page_without_h1_raises_with_the_url():
    with pytest.raises(ValueError, match="brand/3-himalaya"):
        parse_brand("Himalaya", BRAND_URL, "<html><body><p>Przerwa techniczna</p></body></html>")


def test_brand_page_with_an_accordion_without_heading_has_no_faq_title():
    html = (
        '<div id="js-product-list-header"><h1>X</h1><div id="manufacturer-description">'
        '<p>Tekst</p><div class="manufacturer__faq"><div class="accordion-item">'
        '<h3 class="accordion-header"><button>Pytanie?</button></h3>'
        '<div class="accordion-body"><p>Odpowiedź.</p></div></div></div></div></div>'
    )
    brand = parse_brand("X", "https://www.magiczne-indie.pl/brand/9-x", html)
    assert brand.faq_title is None
    assert [(i.question, i.answer) for i in brand.faq] == [("Pytanie?", "<p>Odpowiedź.</p>")]
    assert brand.description == "<p>Tekst</p>"


def test_brand_index_gives_each_brand_once_with_its_page():
    index = parse_brand_index("https://www.magiczne-indie.pl/producenci", read_fixture("brand_index.html"))
    assert index["himalaya"] == ("Himalaya", BRAND_URL)
    # Matched without case, and an apostrophe written as an entity is the same as a plain one
    assert index["ayush"][0] == "AYUSH"
    assert index["himalaya's dreams"][1] == "https://www.magiczne-indie.pl/brand/199-himalaya-s-dreams"
    assert len(index) == 7
    # Links that are not brand pages (the cart) are left out
    assert all("/brand/" in url for _, url in index.values())
