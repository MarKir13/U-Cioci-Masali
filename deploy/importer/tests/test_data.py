"""Loading and validating the scraped results (importer/data.py)."""

import json
import shutil
from pathlib import Path

import pytest

from importer import data

RESULTS = Path(__file__).resolve().parents[3] / "scraper-results"

PRODUCT = {
    "id": 100,
    "url": "https://www.magiczne-indie.pl/100-kredka.html",
    "name": "Kredka",
    "description": "<p>Opis</p>",
    "price": "14.49",
    "regular_price": "14.49",
    "has_discount": False,
    "vat_rate": 23.0,
    "category_ids": [8],
    "images": [
        {"source_url": "https://www.magiczne-indie.pl/1-product_main_2x/k.jpg", "local_path": "images/100-1.jpg"}
    ],
}


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    if not (RESULTS / "schema.json").is_file():
        pytest.skip("scraper-results/schema.json not found")
    shutil.copy(RESULTS / "schema.json", tmp_path / "schema.json")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "100-1.jpg").write_bytes(b"jpeg")
    return tmp_path


def write_products(data_dir: Path, *products: dict) -> None:
    lines = [json.dumps(p, ensure_ascii=False) for p in products]
    (data_dir / "products.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_a_valid_product_is_loaded(data_dir):
    write_products(data_dir, PRODUCT)
    products, rejected, unreadable = data.load_products(data_dir, data.load_schema(data_dir))
    assert [p["id"] for p in products] == [100]
    assert rejected == []
    assert unreadable == []


def test_a_product_without_a_name_is_rejected_with_the_reason(data_dir):
    write_products(data_dir, {**PRODUCT, "name": ""})
    products, rejected, _ = data.load_products(data_dir, data.load_schema(data_dir))
    assert products == []
    assert rejected[0][0] == 100
    assert rejected[0][1].startswith("name:")


def test_loading_does_not_check_image_files(data_dir):
    # A subset run selects its products first, so a missing image of another product must not reject it here
    write_products(data_dir, PRODUCT)
    (data_dir / "images" / "100-1.jpg").unlink()
    products, rejected, _ = data.load_products(data_dir, data.load_schema(data_dir))
    assert [p["id"] for p in products] == [100]
    assert rejected == []


def test_a_product_whose_image_file_is_missing_is_rejected(data_dir):
    (data_dir / "images" / "100-1.jpg").unlink()
    products, rejected = data.with_images([PRODUCT], data_dir)
    assert products == []
    assert rejected == [(100, "image file missing: images/100-1.jpg")]


def test_only_the_given_products_need_their_images(data_dir):
    # Product 200's image is not on disk, as in a subset run with only the subset archive unpacked
    other = {**PRODUCT, "id": 200, "images": [{**PRODUCT["images"][0], "local_path": "images/200-2.jpg"}]}
    products, rejected = data.with_images([PRODUCT], data_dir)
    assert [p["id"] for p in products] == [100]
    assert rejected == []
    products, rejected = data.with_images([PRODUCT, other], data_dir)
    assert [p["id"] for p in products] == [100]
    assert [source_id for source_id, _ in rejected] == [200]


def test_an_unreadable_line_is_reported_and_the_other_products_still_load(data_dir):
    good = json.dumps(PRODUCT, ensure_ascii=False)
    (data_dir / "products.jsonl").write_text(f'{{"id": 7, "name": "cut off\n[1, 2]\n{good}\n', encoding="utf-8")
    products, rejected, unreadable = data.load_products(data_dir, data.load_schema(data_dir))
    assert [p["id"] for p in products] == [100]
    assert rejected == []
    assert [number for number, _ in unreadable] == [1, 2]
    assert unreadable[0][1].startswith("not valid JSON")
    assert unreadable[1][1] == "not a JSON object"


def test_the_real_categories_are_valid():
    if not (RESULTS / "categories.json").is_file():
        pytest.skip("scraper-results not found")
    categories, rejected = data.load_categories(RESULTS, data.load_schema(RESULTS))
    assert rejected == []
    assert len(categories) == 160
