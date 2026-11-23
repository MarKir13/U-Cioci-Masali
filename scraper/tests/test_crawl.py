"""Tests of the full crawl. No network: a fake shop serves small pages built below."""

import html
import json
import logging

import pytest
import requests

from scraper.__main__ import main
from scraper.crawl import (
    Crawler,
    Listing,
    PageCache,
    backfill_from_cache,
    category_positions,
    load_lines,
    save_lines,
)
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


def subcategory_links(category_id: int) -> str:
    """The block of links to the subcategories of `category_id`, as the source shows it under the description."""
    children = [child for child, (_, _, parent_id) in CATEGORIES.items() if parent_id == category_id]
    if not children:
        return ""
    links = "".join(f'<a class="subcategory__link" href="{category_url(c)}">{CATEGORIES[c][1]}</a>' for c in children)
    return f'<div class="subcategory"><div class="subcategory__list">{links}</div></div>'


def category_page(category_id: int, products: list[int], next_page: str | None = None) -> str:
    """A listing page: name, breadcrumb, subcategory links, product tiles and the "next" button."""
    tiles = "".join(f'<article class="product-miniature"><a href="{product_url(p)}">x</a></article>' for p in products)
    if next_page:
        button = f'<button class="next" data-ps-data="{next_page}">Następna</button>'
    else:
        button = '<button class="next disabled">Następna</button>'
    return (
        f'<h1 class="page-title-section">{CATEGORIES[category_id][1]}</h1>'
        f"{breadcrumb(category_path(category_id))}"
        f"{subcategory_links(category_id)}"
        f'<div id="js-product-list">{tiles}</div>{button}'
    )


def product_page(product_id: int, overrides: dict | None = None, with_breadcrumb: bool = True) -> str:
    """A product page with the data-product JSON and the breadcrumb of its default category.

    `overrides` replaces fields of the data-product JSON; `with_breadcrumb=False` leaves the breadcrumb out.
    """
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
    data.update(overrides or {})
    items = [*category_path(default_category), (data["name"], product_url(product_id))]
    crumbs = breadcrumb(items) if with_breadcrumb else ""
    return f"<div class=\"js-product-details\" data-product='{html.escape(json.dumps(data))}'></div>{crumbs}"


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


# ---------- Descriptions ----------


def test_short_description_is_used_when_the_long_one_is_empty(tmp_path):
    pages = shop_pages()
    pages[product_url(102)] = product_page(
        102, {"description": "<p></p>\r\n<p></p>", "description_short": "<p>Krótki</p>"}
    )
    make_crawler(pages, tmp_path)[0].run()
    assert saved_products(tmp_path)[102]["description"] == "<p>Krótki</p>"


def test_long_description_wins_over_the_short_one(tmp_path):
    pages = shop_pages()
    pages[product_url(102)] = product_page(102, {"description": "<p>Długi</p>", "description_short": "<p>Krótki</p>"})
    make_crawler(pages, tmp_path)[0].run()
    assert saved_products(tmp_path)[102]["description"] == "<p>Długi</p>"


def test_product_without_any_description_is_rejected_with_the_reason(tmp_path):
    pages = shop_pages()
    pages[product_url(102)] = product_page(102, {"description": "", "description_short": ""})
    make_crawler(pages, tmp_path)[0].run()

    assert 102 not in saved_products(tmp_path)
    rejected = json.loads((tmp_path / "results" / "rejected.json").read_text(encoding="utf-8"))
    assert [(entry["id"], entry["url"]) for entry in rejected] == [(102, product_url(102))]
    assert "description" in rejected[0]["reason"]


# ---------- Backfilling the short description and the promotion end ----------


def crawl_without_short_descriptions(tmp_path, pages: dict) -> None:
    """A crawl that fills the cache, then products saved as an older crawl did: no short description, no
    promotion end, and an image already downloaded."""
    make_crawler(pages, tmp_path, cache=True)[0].run()
    products_file = tmp_path / "results" / "products.jsonl"
    records = load_lines(products_file)
    for record in records:
        del record["description_short"]
        del record["promo_end"]
        record["images"][0]["local_path"] = f"images/{record['id']}-1.jpg"
    save_lines(products_file, records)


def test_backfill_adds_the_short_description_and_keeps_the_rest(tmp_path):
    pages = shop_pages()
    pages[product_url(102)] = product_page(102, {"description_short": "<p>Krótki</p>"})
    crawl_without_short_descriptions(tmp_path, pages)
    before = saved_products(tmp_path)

    assert backfill_from_cache(tmp_path / "results" / "products.jsonl", PageCache(tmp_path / "cache")) == 0

    after = saved_products(tmp_path)
    assert after[102]["description_short"] == "<p>Krótki</p>"
    assert after[101]["description_short"] is None
    for product_id, record in after.items():
        new_fields = {"description_short": None, "promo_end": None}
        assert {**record, **new_fields} == {**before[product_id], **new_fields}
        assert record["images"][0]["local_path"] == f"images/{product_id}-1.jpg"


def test_second_backfill_changes_nothing(tmp_path, caplog):
    pages = shop_pages()
    pages[product_url(102)] = product_page(102, {"description_short": "<p>Krótki</p>"})
    crawl_without_short_descriptions(tmp_path, pages)
    products_file = tmp_path / "results" / "products.jsonl"
    backfill_from_cache(products_file, PageCache(tmp_path / "cache"))
    first = products_file.read_bytes()

    with caplog.at_level(logging.INFO):
        assert backfill_from_cache(products_file, PageCache(tmp_path / "cache")) == 0
    assert products_file.read_bytes() == first
    assert "4 products, 0 changed, 4 unchanged, 1 with a short description, 0 with a promotion end" in caplog.text


def test_backfill_adds_the_promotion_end_and_keeps_the_prices(tmp_path):
    pages = shop_pages()
    discount = {
        "price_amount": 15.99,
        "has_discount": True,
        "specific_prices": {"reduction": "4.00", "from": "0000-00-00 00:00:00", "to": "2026-11-14 23:59:00"},
    }
    pages[product_url(102)] = product_page(102, discount)
    crawl_without_short_descriptions(tmp_path, pages)
    before = saved_products(tmp_path)

    assert backfill_from_cache(tmp_path / "results" / "products.jsonl", PageCache(tmp_path / "cache")) == 0

    after = saved_products(tmp_path)
    assert after[102]["promo_end"] == "2026-11-14T23:59:00"
    assert after[102]["price"] == before[102]["price"] == "15.99"
    assert after[101]["promo_end"] is None


def test_backfill_keeps_a_product_whose_page_is_not_cached_and_fails(tmp_path, caplog):
    crawl_without_short_descriptions(tmp_path, shop_pages())
    cache = PageCache(tmp_path / "cache")
    cache._path(product_url(103)).unlink()
    before = saved_products(tmp_path)

    with caplog.at_level(logging.WARNING):
        assert backfill_from_cache(tmp_path / "results" / "products.jsonl", cache) == 1

    assert saved_products(tmp_path)[103] == before[103]
    assert "Product 103: page not in the cache" in caplog.text


# ---------- Categories that are not in the shop ----------


def test_category_ids_the_shop_does_not_have_are_dropped(tmp_path):
    """Default category 99 has no page in the sitemap; the breadcrumb still gives the real categories."""
    pages = shop_pages()
    pages[product_url(102)] = product_page(102, {"id_category_default": 99})
    make_crawler(pages, tmp_path)[0].run()
    assert saved_products(tmp_path)[102]["category_ids"] == [10, 11]  # the breadcrumb, without 99


def test_product_in_no_real_category_is_rejected(tmp_path, caplog):
    pages = shop_pages()
    pages[category_url(10)] = category_page(10, [101, 103])  # 102 is on no listing either
    pages[product_url(102)] = product_page(102, {"id_category_default": 99}, with_breadcrumb=False)
    with caplog.at_level(logging.WARNING):
        make_crawler(pages, tmp_path)[0].run()

    assert sorted(saved_products(tmp_path)) == [101, 103, 104]
    rejected = json.loads((tmp_path / "results" / "rejected.json").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in rejected] == [102]
    assert "[99]" in rejected[0]["reason"]
    assert "not categories of the shop" not in caplog.text  # nothing was left of it to keep


def test_products_saved_by_an_earlier_run_are_cleaned_too(tmp_path):
    """Before this check existed a full run saved category ids 1 and 99; the next run fixes them."""
    pages = shop_pages()
    pages[category_url(10)] = category_page(10, [101, 103])  # 102 is on no listing
    pages[product_url(102)] = product_page(102, {"id_category_default": 99}, with_breadcrumb=False)
    make_crawler(pages, tmp_path)[0].run()
    assert 102 not in saved_products(tmp_path)  # this run already leaves it out

    # Put back what the old version would have saved
    products_file = tmp_path / "results" / "products.jsonl"
    records = load_lines(products_file)
    for record in records:
        if record["id"] == 101:
            record["category_ids"].append(1)
    records.append({**records[0], "id": 102, "url": product_url(102), "category_ids": [99]})
    products_file.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    images = tmp_path / "results" / "images"
    images.mkdir()
    (images / "102-1.jpg").write_bytes(b"x")
    (images / "101-1.jpg").write_bytes(b"x")

    make_crawler(pages, tmp_path)[0].run()
    products = saved_products(tmp_path)
    assert products[101]["category_ids"] == [11, 10, 50]
    assert 102 not in products
    assert not (images / "102-1.jpg").exists()  # the image of a removed product goes too
    assert (images / "101-1.jpg").exists()


def test_a_test_run_does_not_touch_category_ids(tmp_path):
    """With --limit only some categories are saved, so ids of the others are not "unknown"."""
    crawler, _ = make_crawler(shop_pages(), tmp_path, limit=1)
    crawler.run()
    assert crawler.known_categories is None
    assert not (tmp_path / "results" / "rejected.json").exists()


# ---------- Empty categories ----------


def test_empty_categories_helper_keeps_the_parent_of_a_filled_subcategory():
    from scraper.crawl import empty_categories

    categories = {
        1: {"id": 1, "parent_id": None},
        2: {"id": 2, "parent_id": 1},
        3: {"id": 3, "parent_id": None},
        4: {"id": 4, "parent_id": 3},
    }
    products = {10: {"category_ids": [2]}}
    assert empty_categories(categories, products) == [3, 4]


def test_run_adds_descriptions_to_categories_saved_without_one(tmp_path):
    """categories.json from before descriptions were scraped gets them on the next run, from the cache."""
    pages = shop_pages()
    pages[category_url(10)] = pages[category_url(10)].replace(
        '<div id="js-product-list">',
        '<div id="category-description"><p>Opis kategorii</p></div><div id="js-product-list">',
    )
    crawler, _ = make_crawler(pages, tmp_path, cache=True)
    crawler.run()
    path = tmp_path / "results" / "categories.json"
    old_records = [{k: v for k, v in c.items() if k != "description"} for c in json.loads(path.read_text("utf-8"))]
    path.write_text(json.dumps(old_records), encoding="utf-8")

    crawler, shop = make_crawler(pages, tmp_path, cache=True)
    crawler.run()

    categories = saved_categories(tmp_path)
    assert categories[10]["description"] == "<p>Opis kategorii</p>"
    assert categories[11]["description"] is None
    assert not [url for url in shop.calls if url in (category_url(10), category_url(11))]


# ---------- Category positions ----------


def category(category_id: int, parent_id: int | None) -> dict:
    return {
        "id": category_id,
        "name": f"Kategoria {category_id}",
        "url": f"{BASE}/{category_id}-k",
        "parent_id": parent_id,
    }


def test_full_run_saves_the_position_of_every_category(tmp_path):
    """Top-level 10 and 50 by id; 11 is the only subcategory linked on the page of 10."""
    make_crawler(shop_pages(), tmp_path)[0].run()
    categories = saved_categories(tmp_path)
    assert {c: categories[c]["position"] for c in categories} == {10: 1, 11: 1, 50: 2}
    listings = json.loads((tmp_path / "results" / "listings.json").read_text(encoding="utf-8"))
    assert listings["10"]["subcategories"] == [11]
    assert listings["11"]["subcategories"] == []


def test_subcategories_follow_the_order_of_the_parent_page_not_their_ids():
    """As on /8-kosmetyki: Kosmetyki BIO (360) first, Higiena i akcesoria (36) last."""
    categories = {c: category(c, 8) for c in (36, 37, 360)} | {8: category(8, None)}
    listings = {8: Listing(subcategories=[360, 37, 36])}
    positions = category_positions(categories, listings)
    assert [positions[c] for c in (360, 37, 36)] == [1, 2, 3]


def test_positions_have_no_gap_and_unlinked_subcategories_come_last_by_id():
    """99 is linked but was removed as empty; 45 and 40 are not linked, so they follow the linked 37 by id."""
    categories = {c: category(c, 8) for c in (37, 40, 45)} | {8: category(8, None)}
    listings = {8: Listing(subcategories=[99, 37])}
    assert category_positions(categories, listings) == {8: 1, 37: 1, 40: 2, 45: 3}


def test_top_level_categories_and_children_of_an_unread_page_are_ordered_by_id():
    categories = {c: category(c, None) for c in (193, 8, 80)} | {c: category(c, 80) for c in (85, 81)}
    listings = {80: Listing(subcategories=None)}
    assert category_positions(categories, listings) == {8: 1, 80: 2, 193: 3, 81: 1, 85: 2}


def forget_subcategories(tmp_path) -> None:
    """Make the saved results look like a run from before positions were scraped."""
    listings_file = tmp_path / "results" / "listings.json"
    listings = json.loads(listings_file.read_text(encoding="utf-8"))
    for listing in listings.values():
        del listing["subcategories"]
    listings_file.write_text(json.dumps(listings), encoding="utf-8")
    categories_file = tmp_path / "results" / "categories.json"
    records = [{k: v for k, v in c.items() if k != "position"} for c in json.loads(categories_file.read_text("utf-8"))]
    categories_file.write_text(json.dumps(records), encoding="utf-8")


def test_run_adds_positions_to_categories_saved_without_one(tmp_path):
    """Results from before positions were scraped get them on the next run, from the cache."""
    make_crawler(shop_pages(), tmp_path, cache=True)[0].run()
    forget_subcategories(tmp_path)

    crawler, shop = make_crawler(shop_pages(), tmp_path, cache=True)
    crawler.run()

    categories = saved_categories(tmp_path)
    assert {c: categories[c]["position"] for c in categories} == {10: 1, 11: 1, 50: 2}
    assert not [url for url in shop.calls if url in (category_url(10), category_url(11), category_url(50))]


def test_unreadable_parent_page_leaves_its_subcategories_by_id_until_the_next_run(tmp_path, caplog):
    make_crawler(shop_pages(), tmp_path)[0].run()
    forget_subcategories(tmp_path)
    pages = shop_pages()
    pages[category_url(10)] = requests.ConnectionError("connection reset")

    with caplog.at_level(logging.WARNING):
        make_crawler(pages, tmp_path)[0].run()
    assert saved_categories(tmp_path)[11]["position"] == 1
    assert "Subcategory order of category 10 is unknown until the next run" in caplog.text
    listings = json.loads((tmp_path / "results" / "listings.json").read_text(encoding="utf-8"))
    assert listings["10"].get("subcategories") is None  # still unknown, so the next run reads the page again


def test_positions_command_reads_only_the_pages_of_parents(tmp_path):
    """Results from before positions were scraped: robots.txt and the page of 10, the only parent. No sitemap,
    no product, and not the pages of 11 and 50, which have no subcategories to order."""
    make_crawler(shop_pages(), tmp_path)[0].run()
    forget_subcategories(tmp_path)
    products_before = (tmp_path / "results" / "products.jsonl").read_text(encoding="utf-8")

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    assert crawler.run_positions() == 0

    assert shop.calls == [f"{BASE}/robots.txt", category_url(10)]
    categories = saved_categories(tmp_path)
    assert {c: categories[c]["position"] for c in categories} == {10: 1, 11: 1, 50: 2}
    assert (tmp_path / "results" / "products.jsonl").read_text(encoding="utf-8") == products_before


def test_positions_command_without_saved_categories_fails(tmp_path, caplog):
    crawler, _ = make_crawler(shop_pages(), tmp_path)
    with caplog.at_level(logging.ERROR):
        assert crawler.run_positions() == 1
    assert "No saved categories" in caplog.text


def test_second_run_leaves_the_positions_unchanged(tmp_path, caplog):
    make_crawler(shop_pages(), tmp_path)[0].run()
    with caplog.at_level(logging.INFO):
        make_crawler(shop_pages(), tmp_path)[0].run()
    assert "Category positions: 0 set or changed, 3 unchanged" in caplog.text


def add_empty_category(tmp_path) -> None:
    path = tmp_path / "results" / "categories.json"
    categories = json.loads(path.read_text(encoding="utf-8"))
    categories.append({"id": 12, "name": "Pusta", "url": f"{BASE}/12-pusta", "parent_id": 10})
    path.write_text(json.dumps(categories), encoding="utf-8")


def test_category_without_products_is_removed(tmp_path, caplog):
    make_crawler(shop_pages(), tmp_path)[0].run()
    add_empty_category(tmp_path)
    with caplog.at_level(logging.WARNING):
        make_crawler(shop_pages(), tmp_path)[0].run()
    assert sorted(saved_categories(tmp_path)) == [10, 11, 50]
    assert "Category 12 Pusta has no products, removing it" in caplog.text


def test_no_category_is_removed_while_a_product_page_failed_to_download(tmp_path, caplog):
    """The failed product may be the only one in a category, so the category only looks empty."""
    make_crawler(shop_pages(), tmp_path)[0].run()
    add_empty_category(tmp_path)
    products_file = tmp_path / "results" / "products.jsonl"
    records = [r for r in load_lines(products_file) if r["id"] != 103]
    products_file.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    pages = shop_pages()
    pages[product_url(103)] = requests.ConnectionError("connection reset")

    with caplog.at_level(logging.WARNING):
        make_crawler(pages, tmp_path)[0].run()
    assert 12 in saved_categories(tmp_path)
    assert "no empty category is removed" in caplog.text


def test_known_empty_category_is_skipped_without_an_error(tmp_path, caplog):
    crawler, shop = make_crawler(shop_pages(), tmp_path, empty_category_ids=(11,))
    with caplog.at_level(logging.INFO):
        crawler.run()
    assert category_url(11) not in shop.calls
    assert "Skipping category 11" in caplog.text
    assert "ERROR" not in [record.levelname for record in caplog.records]


# ---------- Command line ----------


@pytest.mark.parametrize("value", ["0", "-3", "abc"])
def test_limit_must_be_a_positive_whole_number(value, capsys):
    with pytest.raises(SystemExit):
        main(["crawl", "--limit", value])
    assert "--limit" in capsys.readouterr().err
