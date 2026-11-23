"""Tests of the brand crawl. No network: a fake shop serves the saved brand pages."""

import json
import logging
from pathlib import Path

from test_crawl import FakeShop

from scraper import config
from scraper.brands import BrandCrawler, brand_names
from scraper.crawl import PageCache, append_line
from scraper.http_client import HttpClient
from scraper.models import Brand

BASE = "https://www.magiczne-indie.pl"
FIXTURES = Path(__file__).parent / "fixtures"
INDEX = f"{BASE}/producenci"
HIMALAYA = f"{BASE}/brand/3-himalaya"
DABUR = f"{BASE}/brand/4-dabur"
VICCO = f"{BASE}/brand/5-vicco"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def shop_pages() -> dict[str, str]:
    return {
        f"{BASE}/robots.txt": "User-agent: *\nDisallow: /koszyk\n",
        INDEX: fixture("brand_index.html"),
        HIMALAYA: fixture("brand_with_seo_faq.html"),
        DABUR: fixture("brand_with_description_only.html"),
        VICCO: fixture("brand_without_description.html"),
    }


def write_products(tmp_path, brands: list[str | None]) -> None:
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)
    for number, brand in enumerate(brands, start=1):
        append_line(results / "products.jsonl", {"id": number, "brand": brand})


def make_crawler(pages: dict, tmp_path, cache=False, **kwargs) -> tuple[BrandCrawler, FakeShop]:
    shop = FakeShop(pages)
    client = HttpClient(base_url=BASE, session=shop, sleep=lambda seconds: None, max_retries=1)
    page_cache = PageCache(tmp_path / "cache") if cache else None
    return BrandCrawler(client, results_dir=tmp_path / "results", cache=page_cache, **kwargs), shop


def saved(tmp_path) -> dict[str, dict]:
    data = json.loads((tmp_path / "results" / "brands.json").read_text(encoding="utf-8"))
    return {brand["name"]: brand for brand in data}


def test_brands_come_from_the_products_once_each_in_alphabetical_order(tmp_path):
    write_products(tmp_path, ["Vicco", "Dabur", None, "dabur", "Himalaya", "Himalaya's Dreams", "Dabur"])
    assert brand_names(tmp_path / "results" / "products.jsonl") == ["Dabur", "Himalaya", "Himalaya's Dreams", "Vicco"]


def test_himalaya_has_its_title_text_and_four_questions(tmp_path):
    write_products(tmp_path, ["Himalaya"])
    crawler, _ = make_crawler(shop_pages(), tmp_path)
    assert crawler.run() == 0

    himalaya = saved(tmp_path)["Himalaya"]
    assert himalaya["url"] == HIMALAYA
    assert himalaya["title"] == "Himalaya Herbals – oryginalne suplementy i kosmetyki ajurwedyjskie"
    assert himalaya["description"].count("<h2>") == 4
    assert [item["question"] for item in himalaya["faq"]][0] == "Na co jest Himalaya?"
    assert len(himalaya["faq"]) == 4


def test_a_brand_with_a_similar_name_is_a_separate_brand(tmp_path):
    write_products(tmp_path, ["Himalaya", "Himalaya's Dreams"])
    pages = shop_pages()
    pages[f"{BASE}/brand/199-himalaya-s-dreams"] = fixture("brand_without_description.html")
    crawler, shop = make_crawler(pages, tmp_path)
    crawler.run()

    brands = saved(tmp_path)
    assert brands["Himalaya's Dreams"]["url"] == f"{BASE}/brand/199-himalaya-s-dreams"
    assert brands["Himalaya's Dreams"]["faq"] == []
    assert len(brands["Himalaya"]["faq"]) == 4


def test_a_brand_without_a_page_is_saved_with_its_name_and_reported(tmp_path, caplog):
    write_products(tmp_path, ["Himalaya", "Marka bez strony"])
    crawler, shop = make_crawler(shop_pages(), tmp_path)
    with caplog.at_level(logging.WARNING):
        assert crawler.run() == 0

    assert saved(tmp_path)["Marka bez strony"] == {
        "name": "Marka bez strony",
        "url": None,
        "title": None,
        "description": None,
        "faq_title": None,
        "faq": [],
        "meta_title": None,
        "meta_description": None,
    }
    assert "Brands without a page in the source shop (1): Marka bez strony" in caplog.text


def test_a_page_without_a_description_is_saved_and_reported(tmp_path, caplog):
    write_products(tmp_path, ["Vicco"])
    crawler, _ = make_crawler(shop_pages(), tmp_path)
    with caplog.at_level(logging.INFO):
        assert crawler.run() == 0
    assert saved(tmp_path)["Vicco"]["description"] is None
    assert saved(tmp_path)["Vicco"]["title"] == "Vicco"
    assert "Brands whose page has no description (1): Vicco" in caplog.text


def test_second_run_downloads_nothing(tmp_path):
    write_products(tmp_path, ["Himalaya", "Dabur", "Vicco"])
    make_crawler(shop_pages(), tmp_path)[0].run()
    crawler, shop = make_crawler(shop_pages(), tmp_path)
    assert crawler.run() == 0
    assert shop.calls == []
    assert len(saved(tmp_path)) == 3


def test_limited_run_is_continued_by_the_next_one(tmp_path):
    write_products(tmp_path, ["Himalaya", "Dabur", "Vicco"])
    crawler, first = make_crawler(shop_pages(), tmp_path, limit=1)
    crawler.run()
    assert list(saved(tmp_path)) == ["Dabur"]

    crawler, second = make_crawler(shop_pages(), tmp_path)
    crawler.run()
    assert sorted(saved(tmp_path)) == ["Dabur", "Himalaya", "Vicco"]
    assert DABUR not in second.calls


def test_ctrl_c_keeps_saved_brands_and_the_next_run_finishes(tmp_path):
    write_products(tmp_path, ["Himalaya", "Dabur", "Vicco"])
    pages = shop_pages()
    pages[HIMALAYA] = KeyboardInterrupt()
    crawler, _ = make_crawler(pages, tmp_path)
    assert crawler.run() == 130
    assert list(saved(tmp_path)) == ["Dabur"]

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    assert crawler.run() == 0
    assert sorted(saved(tmp_path)) == ["Dabur", "Himalaya", "Vicco"]
    assert DABUR not in shop.calls


def test_a_page_that_fails_is_not_saved_and_is_tried_again(tmp_path, caplog):
    write_products(tmp_path, ["Himalaya", "Dabur"])
    pages = shop_pages()
    pages[HIMALAYA] = 500
    crawler, _ = make_crawler(pages, tmp_path)
    with caplog.at_level(logging.ERROR):
        assert crawler.run() == 1
    assert list(saved(tmp_path)) == ["Dabur"]

    crawler, shop = make_crawler(shop_pages(), tmp_path)
    assert crawler.run() == 0
    assert HIMALAYA in shop.calls
    assert sorted(saved(tmp_path)) == ["Dabur", "Himalaya"]


def test_a_page_without_h1_is_logged_and_not_saved(tmp_path, caplog):
    write_products(tmp_path, ["Dabur"])
    pages = shop_pages()
    pages[DABUR] = "<html><body>Przerwa techniczna</body></html>"
    crawler, _ = make_crawler(pages, tmp_path)
    with caplog.at_level(logging.ERROR):
        assert crawler.run() == 1
    assert "no brand name" in caplog.text


def test_the_index_is_not_downloaded_when_nothing_is_left(tmp_path):
    write_products(tmp_path, ["Dabur"])
    make_crawler(shop_pages(), tmp_path)[0].run()
    pages = shop_pages()
    pages[INDEX] = 500
    crawler, shop = make_crawler(pages, tmp_path)
    assert crawler.run() == 0
    assert INDEX not in shop.calls


def test_pages_from_the_cache_are_not_downloaded_again(tmp_path):
    write_products(tmp_path, ["Dabur", "Himalaya"])
    make_crawler(shop_pages(), tmp_path, cache=True)[0].run()
    (tmp_path / "results" / "brands.json").unlink()
    crawler, shop = make_crawler(shop_pages(), tmp_path, cache=True)
    assert crawler.run() == 0
    assert shop.calls == [f"{BASE}/robots.txt"]


def test_a_brand_page_blocked_by_robots_txt_is_not_requested(tmp_path):
    write_products(tmp_path, ["Dabur", "Himalaya"])
    pages = shop_pages()
    pages[f"{BASE}/robots.txt"] = "User-agent: *\nDisallow: /brand/4-dabur\n"
    crawler, shop = make_crawler(pages, tmp_path)
    assert crawler.run() == 1  # the blocked brand counts as failed, so the next run tries it again
    assert DABUR not in shop.calls
    assert list(saved(tmp_path)) == ["Himalaya"]


def test_results_are_utf8_without_escapes(tmp_path):
    write_products(tmp_path, ["Himalaya"])
    make_crawler(shop_pages(), tmp_path)[0].run()
    text = (tmp_path / "results" / "brands.json").read_text(encoding="utf-8")
    assert "Najczęstsze pytania o Himalaya" in text
    assert "\\u" not in text


def test_the_committed_brands_json_is_valid():
    """brands.json in scraper-results/ passes the model, is UTF-8 and has Himalaya with its FAQ."""
    path = config.BRANDS_FILE
    records = json.loads(path.read_text(encoding="utf-8"))
    brands = {}
    for record in records:
        brand = Brand.model_validate(record)  # raises if the file broke the schema or holds script, style or on*=
        assert brand.name not in brands, f"{brand.name} twice"
        brands[brand.name] = brand
    assert brands["Himalaya"].title
    assert brands["Himalaya"].description
    assert len(brands["Himalaya"].faq) == 4
