"""The image archives for the GitHub Release (scraper/publish.py): the full set and the init command's subset."""

import json
import tarfile

import pytest

from scraper.__main__ import category_ids
from scraper.publish import make_archive

# 8 Kosmetyki > 38 Do włosów > 104 Olejki, and 193 Żywność > 85 Przyprawy
CATEGORIES = [
    {"id": 8, "name": "Kosmetyki", "url": "https://x/8", "parent_id": None},
    {"id": 38, "name": "Do włosów", "url": "https://x/38", "parent_id": 8},
    {"id": 104, "name": "Olejki", "url": "https://x/104", "parent_id": 38},
    {"id": 193, "name": "Żywność", "url": "https://x/193", "parent_id": None},
    {"id": 85, "name": "Przyprawy", "url": "https://x/85", "parent_id": 193},
]


def product(product_id: int, category_ids: list[int], image_count: int = 1) -> dict:
    images = [
        {"source_url": f"https://x/{i}.jpg", "local_path": f"images/{product_id}-{i}.jpg"} for i in range(image_count)
    ]
    return {"id": product_id, "category_ids": category_ids, "images": images}


@pytest.fixture
def results(tmp_path):
    products = [product(1, [104, 38, 8], image_count=2), product(2, [85, 193]), product(3, [8])]
    (tmp_path / "categories.json").write_text(json.dumps(CATEGORIES), encoding="utf-8")
    lines = "".join(json.dumps(p) + "\n" for p in products)
    (tmp_path / "products.jsonl").write_text(lines, encoding="utf-8")
    (tmp_path / "images").mkdir()
    for p in products:
        for image in p["images"]:
            (tmp_path / image["local_path"]).write_bytes(b"jpeg")
    return tmp_path


def names(archive_path) -> list[str]:
    with tarfile.open(archive_path) as archive:
        return sorted(archive.getnames())


def test_the_full_archive_holds_every_image_under_images(results):
    assert make_archive(results) == 0
    assert names(results / "product-images.tar.gz") == [
        "images/1-0.jpg",
        "images/1-1.jpg",
        "images/2-0.jpg",
        "images/3-0.jpg",
    ]


def test_the_subset_holds_the_images_of_the_categories_and_their_subcategories(results):
    # 38 brings in product 1 through its subcategory 104; product 3 is only in 8, the parent, so it stays out
    assert make_archive(results, categories={38, 85}) == 0
    assert names(results / "subset-images.tar.gz") == ["images/1-0.jpg", "images/1-1.jpg", "images/2-0.jpg"]
    assert not (results / "product-images.tar.gz").exists()


def test_a_subset_with_a_missing_image_file_writes_no_archive(results):
    (results / "images" / "2-0.jpg").unlink()
    assert make_archive(results, categories={85}) == 1
    assert not (results / "subset-images.tar.gz").exists()


def test_a_subset_of_unknown_categories_writes_no_archive(results, caplog):
    assert make_archive(results, categories={999}) == 1
    assert not (results / "subset-images.tar.gz").exists()
    assert "No product is in categories [999]" in caplog.text


def test_category_ids_are_read_from_a_comma_separated_list():
    assert category_ids("85,99") == {85, 99}
    assert category_ids(" 85, 99 ,") == {85, 99}
