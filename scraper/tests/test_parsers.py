"""Tests of the parsers on pages saved from the source shop. They do not use the network."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scraper.models import Category
from scraper.parsers import (
    children_by_parent,
    missing_parents,
    next_page_url,
    parse_category,
    parse_product,
    parse_sitemap,
    parse_sitemap_index,
    product_urls,
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
