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
    products, rejected = data.load_products(data_dir, data.load_schema(data_dir))
    assert [p["id"] for p in products] == [100]
    assert rejected == []


def test_a_product_without_a_name_is_rejected_with_the_reason(data_dir):
    write_products(data_dir, {**PRODUCT, "name": ""})
    products, rejected = data.load_products(data_dir, data.load_schema(data_dir))
    assert products == []
    assert rejected[0][0] == 100
    assert rejected[0][1].startswith("name:")


def test_a_product_whose_image_file_is_missing_is_rejected(data_dir):
    write_products(data_dir, PRODUCT)
    (data_dir / "images" / "100-1.jpg").unlink()
    products, rejected = data.load_products(data_dir, data.load_schema(data_dir))
    assert products == []
    assert "image file missing" in rejected[0][1]


def test_the_real_categories_are_valid():
    if not (RESULTS / "categories.json").is_file():
        pytest.skip("scraper-results not found")
    categories, rejected = data.load_categories(RESULTS, data.load_schema(RESULTS))
    assert rejected == []
    assert len(categories) == 160
