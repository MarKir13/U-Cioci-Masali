"""Tests of the family blocks (issue #114) on a saved product page. They do not use the network."""

import json
import logging
from pathlib import Path

from scraper import config
from scraper.crawl import PageCache, save_lines
from scraper.families import build_families, parse_family

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.magiczne-indie.pl/242-olejek-amla-do-wlosow-ciemnych-200ml-dabur.html"


def fixture() -> str:
    return (FIXTURES / "product_with_family.html").read_text(encoding="utf-8")


def test_parse_family_reads_every_row():
    family = parse_family(URL, fixture())

    assert family is not None
    assert family.product_id == 242
    assert [(axis.title, axis.kind, len(axis.options)) for axis in family.axes] == [
        ("Pojemność", "text", 3),
        ("Olejek", "image", 9),
    ]


def test_parse_family_labels_and_ids():
    sizes, oils = parse_family(URL, fixture()).axes

    # A text button is its own label; the current product (a <span> without a link) gets the page's id
    assert [(o.source_id, o.label) for o in sizes.options] == [(706, "100 ml"), (242, "200 ml"), (243, "300 ml")]
    # A photo tile's label is its caption, not the long title of the product
    assert (oils.options[0].source_id, oils.options[0].label) == (242, "Amla")
    assert (oils.options[-1].source_id, oils.options[-1].label) == (6256, "Rycyna")
    assert any(option.label == "Migdał" for option in oils.options)


def test_page_without_family_gives_none():
    html = fixture()
    start = html.index('<nav class="ndx-family"')
    end = html.index("</nav>", start) + len("</nav>")
    assert parse_family(URL, html[:start] + html[end:]) is None


def test_row_without_title_is_kept_with_null_title():
    html = fixture().replace('<p class="ndx-family__legend">Olejek</p>', "", 1)
    family = parse_family(URL, html)
    assert family is not None
    assert family.axes[1].title is None


def test_duplicate_tile_is_rejected_and_logged(caplog):
    html = fixture().replace("/243-olejek-amla", "/706-olejek-amla", 1)
    with caplog.at_level(logging.ERROR):
        assert parse_family(URL, html) is None
    assert "duplicate source_id" in caplog.text


def test_build_families_from_cache(tmp_path):
    products = tmp_path / "products.jsonl"
    other = "https://www.magiczne-indie.pl/706-olejek.html"
    save_lines(
        products,
        [
            {"id": 242, "url": URL, "family": [other]},
            {"id": 5, "url": "https://www.magiczne-indie.pl/5-x.html", "family": []},  # no family: not read
        ],
    )
    cache = PageCache(tmp_path / "cache")
    cache.put(URL, fixture())
    out = tmp_path / "families.json"
    shop_copy = tmp_path / "module" / "data" / "families.json"
    shop_copy.parent.mkdir(parents=True)

    assert build_families(products, cache, out, shop_copy) == 0

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert list(saved) == ["242"]
    assert saved["242"][0]["title"] == "Pojemność"  # Polish characters as they are
    assert "Pojemność" in out.read_text(encoding="utf-8")
    assert shop_copy.read_bytes() == out.read_bytes()


def test_build_families_page_missing_from_cache(tmp_path, caplog):
    products = tmp_path / "products.jsonl"
    save_lines(products, [{"id": 242, "url": URL, "family": ["https://www.magiczne-indie.pl/706-x.html"]}])
    out = tmp_path / "families.json"
    out.write_text('{\n"242": []\n}\n', encoding="utf-8")
    shop_copy = tmp_path / "shop" / "families.json"
    shop_copy.parent.mkdir()
    shop_copy.write_text("old copy", encoding="utf-8")

    # Without the cache (a clean clone) the saved families must survive, not be replaced by an empty file
    with caplog.at_level(logging.WARNING):
        assert build_families(products, PageCache(tmp_path / "cache"), out, shop_copy) == 1
    assert out.read_text(encoding="utf-8") == '{\n"242": []\n}\n'
    assert shop_copy.read_text(encoding="utf-8") == "old copy"
    assert "not in the cache" in caplog.text
    assert "left unchanged" in caplog.text


def test_shop_module_has_the_same_families_file():
    """The shop image sees only shop/, so the module keeps a copy; `python -m scraper families` writes both."""
    assert config.SHOP_FAMILIES_FILE.read_bytes() == config.FAMILIES_FILE.read_bytes()
