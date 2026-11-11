"""Tests of the full crawl. No network: a fake shop serves small pages built below."""

import html
import json
import logging

import pytest
import requests

from scraper.__main__ import main
from scraper.crawl import Crawler, PageCache, load_lines
from scraper.http_client import HttpClient

BASE = "https://shop.test"
SITEMAP = f"{BASE}/1_pl_0_sitemap.xml"

# Category tree of the fake shop: id -> (slug, name, parent id)
CATEGORIES = {
    10: ("10-kosmetyki", "Kosmetyki", None),
    11: ("11-olejki", "Olejki do włosów", 10),
    50: ("50-nowosci", "Nowości", None),
}
# Products: id -> default category. 104 is not in the sitemap and appears only on the Nowości listing.
PRODUCTS = {101: 11, 102: 11, 103: 10, 104: 11}
IN_SITEMAP = [101, 102, 103]


def category_url(category_id: int) -> str:
    return f"{BASE}/{CATEGORIES[category_id][0]}"


def product_url(product_id: int) -> str:
    return f"{BASE}/{product_id}-produkt-{product_id}.html"


def breadcrumb(items: list[tuple[str, str]]) -> str:
    elements = [{"position": i, "name": name, "item": url} for i, (name, url) in enumerate(items, start=1)]
    data = {"@type": "BreadcrumbList", "itemListElement": elements}
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def category_path(category_id: int | None) -> list[tuple[str, str]]:
    """Breadcrumb items from the home page down to `category_id`."""
    path = []
    while category_id is not None:
        slug, name, parent_id = CATEGORIES[category_id]
        path.insert(0, (name, f"{BASE}/{slug}"))
        category_id = parent_id
    return [("Strona główna", f"{BASE}/"), *path]


def category_page(category_id: int, products: list[int], next_page: str | None = None) -> str:
    """A listing page: name, breadcrumb, product tiles and the "next" button."""
    tiles = "".join(f'<article class="product-miniature"><a href="{product_url(p)}">x</a></article>' for p in products)
    if next_page:
        button = f'<button class="next" data-ps-data="{next_page}">Następna</button>'
    else:
        button = '<button class="next disabled">Następna</button>'
    return (
        f'<h1 class="page-title-section">{CATEGORIES[category_id][1]}</h1>'
        f"{breadcrumb(category_path(category_id))}"
        f'<div id="js-product-list">{tiles}</div>{button}'
    )


def product_page(product_id: int) -> str:
    """A product page with the data-product JSON and the breadcrumb of its default category."""
    default_category = PRODUCTS[product_id]
    data = {
        "id": product_id,
        "name": f"Olejek łopianowy {product_id}",
        "description": "<p>Opis</p>",
        "price_amount": 19.99,
        "price_without_reduction": 19.99,
        "has_discount": False,
        "rate": 23,
        "id_category_default": default_category,
        "images": [{"bySize": {"product_main_2x": {"url": f"{BASE}/{product_id}0-product_main_2x/p.jpg"}}}],
    }
    items = [*category_path(default_category), (data["name"], product_url(product_id))]
    return f"<div class=\"js-product-details\" data-product='{html.escape(json.dumps(data))}'></div>{breadcrumb(items)}"


def shop_pages() -> dict[str, str]:
    """Every page of the fake shop by URL. Tests change entries to break single pages."""
    sitemap_urls = [category_url(c) for c in CATEGORIES] + [product_url(p) for p in IN_SITEMAP]
    locs = "".join(f"<url><loc><![CDATA[{url}]]></loc></url>" for url in sitemap_urls)
    pages = {
        f"{BASE}/robots.txt": "User-agent: *\nDisallow: /koszyk\n",
        f"{BASE}/1_index_sitemap.xml": (
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<sitemap><loc>{SITEMAP}</loc></sitemap></sitemapindex>"
        ),
        SITEMAP: f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>',
        # Parent categories list the products of their subcategories too
        category_url(10): category_page(10, [101, 102, 103]),
        # Olejki has a page 2, which the crawl does not need: its products have it as default category
        category_url(11): category_page(11, [101], next_page=f"{category_url(11)}?page=2"),
        f"{category_url(11)}?page=2": category_page(11, [102]),
        # Nowości is walked to the end: it is nobody's default category
        category_url(50): category_page(50, [103], next_page=f"{category_url(50)}?page=2"),
        f"{category_url(50)}?page=2": category_page(50, [101, 104]),
    }
    pages.update({product_url(p): product_page(p) for p in PRODUCTS})
    return pages


class FakeShop:
    """Stands in for requests.Session: serves `pages` (404 for anything else) and records every request.

    A page can also be a status code to answer with, or an exception to raise.
    """

    def __init__(self, pages: dict):
        self.headers = {}
        self.pages = pages
        self.calls: list[str] = []

    get_redirect_target = requests.Session.get_redirect_target

    def get(self, url, timeout, allow_redirects=True):
        self.calls.append(url)
        page = self.pages.get(url, 404)
        if isinstance(page, BaseException):
            raise page
        response = requests.Response()
        response.url = url
        response.status_code = page if isinstance(page, int) else 200
        response._content = page.encode("utf-8") if isinstance(page, str) else b""
        response.encoding = "utf-8"
        return response


def make_crawler(pages: dict, tmp_path, cache=False, **kwargs) -> tuple[Crawler, FakeShop]:
    shop = FakeShop(pages)
    client = HttpClient(base_url=BASE, session=shop, sleep=lambda seconds: None, max_retries=1)
    page_cache = PageCache(tmp_path / "cache") if cache else None
    crawler = Crawler(client, results_dir=tmp_path / "results", cache=page_cache, full_listing_ids=(50,), **kwargs)
    return crawler, shop


def saved_products(tmp_path) -> dict[int, dict]:
    return {record["id"]: record for record in load_lines(tmp_path / "results" / "products.jsonl")}


def saved_categories(tmp_path) -> dict[int, dict]:
    data = json.loads((tmp_path / "results" / "categories.json").read_text(encoding="utf-8"))
    return {category["id"]: category for category in data}


# ---------- A complete run ----------


def test_full_run_saves_categories_and_products(tmp_path):
    crawler, _ = make_crawler(shop_pages(), tmp_path)
    assert crawler.run() == 0

    categories = saved_categories(tmp_path)
    assert {c: categories[c]["parent_id"] for c in categories} == {10: None, 11: 10, 50: None}
    assert sorted(saved_products(tmp_path)) == [101, 102, 103, 104]


def test_categories_from_the_page_and_the_listings_are_merged(tmp_path):
    """Default category and breadcrumb from the product page, Nowości from its listing, no duplicates."""
    crawler, _ = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    products = saved_products(tmp_path)

    assert products[101]["category_ids"] == [11, 10, 50]  # Nowości from listing page 2
    assert products[102]["category_ids"] == [11, 10]  # 10 is both in the breadcrumb and on its listing
    assert products[103]["category_ids"] == [10, 50]


def test_product_found_only_on_a_listing_is_downloaded(tmp_path):
    crawler, shop = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert product_url(104) in shop.calls
    assert saved_products(tmp_path)[104]["category_ids"] == [11, 10, 50]


def test_only_the_special_listings_are_walked_past_page_one(tmp_path):
    crawler, shop = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert f"{category_url(50)}?page=2" in shop.calls
    assert f"{category_url(11)}?page=2" not in shop.calls


def test_every_page_is_requested_once(tmp_path):
    crawler, shop = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert len(shop.calls) == len(set(shop.calls))


def test_results_are_utf8_without_escapes(tmp_path):
    crawler, _ = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert "Olejek łopianowy 101" in (tmp_path / "results" / "products.jsonl").read_text(encoding="utf-8")
    assert "Olejki do włosów" in (tmp_path / "results" / "categories.json").read_text(encoding="utf-8")


# ---------- Resuming ----------


def test_second_run_downloads_only_the_sitemap(tmp_path, caplog):
    """Saved categories, finished listings and saved products are all skipped."""
    make_crawler(shop_pages(), tmp_path)[0].run()
    crawler, shop = make_crawler(shop_pages(), tmp_path)

    with caplog.at_level(logging.INFO):
        assert crawler.run() == 0
    assert shop.calls == [f"{BASE}/robots.txt", f"{BASE}/1_index_sitemap.xml", SITEMAP]
    assert "Skipping 4 products already saved" in caplog.text


def test_limited_run_is_continued_by_the_next_one(tmp_path):
    crawler, first = make_crawler(shop_pages(), tmp_path, limit=1)
    crawler.run()
    assert len(saved_categories(tmp_path)) == 1
    assert len(saved_products(tmp_path)) == 1

    crawler, second = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert sorted(saved_products(tmp_path)) == [101, 102, 103, 104]
    # Nothing downloaded by the first run is downloaded again, apart from robots.txt and the sitemap
    repeated = set(first.calls) & set(second.calls)
    assert repeated == {f"{BASE}/robots.txt", f"{BASE}/1_index_sitemap.xml", SITEMAP}


def test_ctrl_c_keeps_saved_results_and_the_next_run_finishes(tmp_path):
    pages = shop_pages()
    pages[product_url(102)] = KeyboardInterrupt()
    crawler, _ = make_crawler(pages, tmp_path)
    assert crawler.run() == 130
    assert sorted(saved_products(tmp_path)) == [101]

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    assert crawler.run() == 0
    assert sorted(saved_products(tmp_path)) == [101, 102, 103, 104]
    assert product_url(101) not in shop.calls


def test_unfinished_listing_continues_where_it_stopped(tmp_path):
    pages = shop_pages()
    pages[f"{category_url(50)}?page=2"] = KeyboardInterrupt()
    make_crawler(pages, tmp_path)[0].run()

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert f"{category_url(50)}?page=2" in shop.calls
    assert category_url(50) not in shop.calls  # page 1 was saved with the category
    assert saved_products(tmp_path)[101]["category_ids"] == [11, 10, 50]


def test_cut_off_last_line_is_removed_and_downloaded_again(tmp_path, caplog):
    make_crawler(shop_pages(), tmp_path)[0].run()
    products_file = tmp_path / "results" / "products.jsonl"
    lines = products_file.read_text(encoding="utf-8").splitlines(keepends=True)
    products_file.write_text("".join(lines[:-1]) + lines[-1][:20], encoding="utf-8")  # as if cut by Ctrl+C

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    with caplog.at_level(logging.WARNING):
        crawler.run()
    assert "incomplete last line" in caplog.text
    assert len(shop.calls) == 4  # robots.txt, 2 sitemaps and the one lost product
    assert sorted(saved_products(tmp_path)) == [101, 102, 103, 104]


def test_broken_line_in_the_middle_is_an_error(tmp_path):
    path = tmp_path / "products.jsonl"
    path.write_text('{"id": 1}\nnot json\n{"id": 2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_lines(path)


def test_cached_pages_are_not_downloaded_again(tmp_path):
    """After a parser fix the results can be rebuilt from the cache, without the shop."""
    make_crawler(shop_pages(), tmp_path, cache=True)[0].run()
    (tmp_path / "results" / "products.jsonl").unlink()

    crawler, shop = make_crawler(shop_pages(), tmp_path, cache=True)
    crawler.run()
    assert sorted(saved_products(tmp_path)) == [101, 102, 103, 104]
    assert shop.calls == [f"{BASE}/robots.txt", f"{BASE}/1_index_sitemap.xml", SITEMAP]


# ---------- Errors ----------


def test_failed_robots_txt_stops_the_run_before_any_other_page(tmp_path, caplog):
    pages = shop_pages()
    pages[f"{BASE}/robots.txt"] = 503
    crawler, shop = make_crawler(pages, tmp_path)

    assert crawler.run() == 1
    assert shop.calls == [f"{BASE}/robots.txt"] * 2  # one attempt and one retry (max_retries=1)
    assert "Could not read robots.txt" in caplog.text


def test_failed_sitemap_stops_the_run(tmp_path):
    pages = shop_pages()
    pages[SITEMAP] = 500
    crawler, shop = make_crawler(pages, tmp_path)
    assert crawler.run() == 1
    assert shop.calls[-1] == SITEMAP


def test_one_failed_page_does_not_stop_the_run(tmp_path, caplog):
    pages = shop_pages()
    pages[product_url(102)] = 404
    pages[product_url(103)] = requests.ConnectionError("connection reset")
    crawler, _ = make_crawler(pages, tmp_path)

    assert crawler.run() == 0
    assert sorted(saved_products(tmp_path)) == [101, 104]
    assert f"Could not download {product_url(102)}" in caplog.text
    assert f"Could not download {product_url(103)}" in caplog.text


def test_page_blocked_by_robots_is_skipped(tmp_path):
    pages = shop_pages()
    pages[f"{BASE}/robots.txt"] = f"User-agent: *\nDisallow: /{product_url(102).rsplit('/', 1)[1]}\n"
    crawler, shop = make_crawler(pages, tmp_path)

    assert crawler.run() == 0
    assert product_url(102) not in shop.calls
    assert 102 not in saved_products(tmp_path)


def test_invalid_product_is_logged_and_skipped(tmp_path, caplog):
    pages = shop_pages()
    pages[product_url(102)] = product_page(102).replace("&quot;rate&quot;: 23", "&quot;rate&quot;: 230")
    crawler, _ = make_crawler(pages, tmp_path)

    assert crawler.run() == 0
    assert 102 not in saved_products(tmp_path)
    assert f"Invalid Product at {product_url(102)}" in caplog.text


def test_page_without_product_data_is_logged_and_skipped(tmp_path, caplog):
    pages = shop_pages()
    pages[product_url(102)] = "<html>maintenance</html>"
    crawler, _ = make_crawler(pages, tmp_path)

    assert crawler.run() == 0
    assert f"Could not parse product {product_url(102)}" in caplog.text


def test_category_left_empty_is_reported(tmp_path, caplog):
    """Nowości lists products, but here none of them could be saved."""
    pages = shop_pages()
    pages[category_url(50)] = category_page(50, [102])
    pages[product_url(102)] = 404
    crawler, _ = make_crawler(pages, tmp_path)

    with caplog.at_level(logging.WARNING):
        crawler.run()
    assert "Category 50 Nowości has products in the source shop but none saved" in caplog.text


def test_failed_listing_page_is_tried_again_next_run(tmp_path):
    pages = shop_pages()
    pages[f"{category_url(50)}?page=2"] = 500
    make_crawler(pages, tmp_path)[0].run()
    listings = json.loads((tmp_path / "results" / "listings.json").read_text(encoding="utf-8"))
    assert listings["50"]["next_page"] == f"{category_url(50)}?page=2"

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert f"{category_url(50)}?page=2" in shop.calls


# ---------- Command line ----------


@pytest.mark.parametrize("value", ["0", "-3", "abc"])
def test_limit_must_be_a_positive_whole_number(value, capsys):
    with pytest.raises(SystemExit):
        main(["crawl", "--limit", value])
    assert "--limit" in capsys.readouterr().err
