"""Tests of verify.py and publish.py on a small made-up set of results. No network."""

import json
import tarfile

import pytest
from PIL import Image

from scraper import config, publish, verify
from scraper.__main__ import main


def write_jpeg(path, size=(900, 600)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path, format="JPEG", quality=50)


def category(category_id, parent_id=None):
    return {
        "id": category_id,
        "name": f"Kategoria {category_id}",
        "url": f"https://shop.test/{category_id}-k",
        "parent_id": parent_id,
    }


def product(product_id, category_ids, images=1):
    return {
        "id": product_id,
        "url": f"https://shop.test/{product_id}-p.html",
        "name": f"Produkt {product_id}",
        "description": "<p>Opis</p>",
        "price": "10.00",
        "regular_price": "10.00",
        "has_discount": False,
        "category_ids": category_ids,
        "images": [
            {"source_url": f"https://shop.test/{i}-product_main_2x/p.jpg", "local_path": f"images/{product_id}-{i}.jpg"}
            for i in range(1, images + 1)
        ],
    }


@pytest.fixture
def results(tmp_path, monkeypatch):
    """Four root categories with two filled subcategories each, a product in every subcategory."""
    monkeypatch.setattr(config, "MIN_PRODUCTS", 8)
    monkeypatch.setattr(config, "MIN_PRODUCTS_WITH_TWO_IMAGES", 2)
    categories, products = [], []
    for root in (1, 2, 3, 4):
        categories.append(category(root))
        for sub in (root * 10 + 1, root * 10 + 2):
            categories.append(category(sub, root))
            products.append(product(sub, [sub, root], images=2 if sub in (11, 12) else 1))
    (tmp_path / "categories.json").write_text(json.dumps(categories), encoding="utf-8")
    (tmp_path / "products.jsonl").write_text("".join(json.dumps(p) + "\n" for p in products), encoding="utf-8")
    for p in products:
        for image in p["images"]:
            write_jpeg(tmp_path / image["local_path"])
    return tmp_path


def failed(results_dir):
    return [check.name for check in verify.verify(results_dir) if not check.ok]


def test_good_results_pass(results):
    assert failed(results) == []
    assert verify.run(results) == 0
    report = (results / "verification-report.md").read_text(encoding="utf-8")
    assert "FAIL" not in report and "PASS" in report


def test_invalid_product_fails_the_schema_check(results):
    with (results / "products.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps({**product(99, [11]), "description": ""}) + "\n")
    assert "No validation errors (schema)" in failed(results)
    assert verify.run(results) == 1


def test_too_few_products_fail(results, monkeypatch):
    monkeypatch.setattr(config, "MIN_PRODUCTS", 9)
    assert failed(results) == ["At least 9 products"]


def test_missing_image_file_fails(results):
    (results / "images" / "11-1.jpg").unlink()
    names = failed(results)
    assert "Every image file listed in products.jsonl exists" in names


def test_product_whose_only_image_is_missing_fails(results):
    (results / "images" / "21-1.jpg").unlink()
    assert "Every product has at least one image file" in failed(results)


def test_too_few_products_with_two_images_fail(results, monkeypatch):
    monkeypatch.setattr(config, "MIN_PRODUCTS_WITH_TWO_IMAGES", 3)
    assert failed(results) == ["At least 3 products have two or more images"]


@pytest.mark.parametrize("size", [(700, 500), (1700, 900)])
def test_image_outside_800_to_1600_px_fails(results, size):
    write_jpeg(results / "images" / "11-1.jpg", size)
    assert len(failed(results)) == 1
    assert "px on the longer side" in failed(results)[0]


def test_image_over_300_kb_fails(results, monkeypatch):
    monkeypatch.setattr(config, "IMAGE_MAX_BYTES", 100)
    assert any("at most 100 bytes" in name for name in failed(results))


def test_png_with_jpg_name_fails(results):
    Image.new("RGB", (900, 600)).save(results / "images" / "11-1.jpg", format="PNG")
    assert any("JPEG" in name for name in failed(results))


def test_image_nobody_uses_fails(results):
    write_jpeg(results / "images" / "999-1.jpg")
    assert failed(results) == ["No image file that no product uses"]


def test_empty_category_fails(results):
    categories = json.loads((results / "categories.json").read_text(encoding="utf-8"))
    categories.append(category(5, 1))
    (results / "categories.json").write_text(json.dumps(categories), encoding="utf-8")
    assert "No empty categories" in failed(results)


def test_fewer_than_four_categories_with_two_filled_subcategories_fail(results):
    lines = (results / "products.jsonl").read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if json.loads(line)["id"] != 42]  # category 4 keeps only one filled subcategory
    (results / "products.jsonl").write_text("\n".join(kept) + "\n", encoding="utf-8")
    names = failed(results)
    assert any(name.startswith("At least 4 categories") for name in names)
    assert "No empty categories" in names  # category 42 is empty now


def test_product_in_unknown_category_fails(results):
    with (results / "products.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(product(98, [11, 77])) + "\n")
    write_jpeg(results / "images" / "98-1.jpg")
    assert failed(results) == ["Every parent and every product category exists"]


def test_big_result_file_fails(results, monkeypatch):
    monkeypatch.setattr(config, "MAX_RESULT_FILE_BYTES", 1000)
    assert any("No result file over" in name for name in failed(results))


def test_images_and_the_archive_do_not_count_as_committed_files(results, monkeypatch):
    monkeypatch.setattr(config, "MAX_RESULT_FILE_BYTES", 100_000)
    (results / config.IMAGES_ARCHIVE.name).write_bytes(b"x" * 200_000)
    write_jpeg(results / "images" / "11-1.jpg", (1600, 1600))  # more than 100 KB is not the point here
    assert not any("No result file over" in name for name in failed(results))


def test_rejected_products_are_listed_in_the_report(results):
    (results / "rejected.json").write_text(
        json.dumps([{"id": 5, "url": "https://shop.test/5-p.html", "reason": "no description"}]), encoding="utf-8"
    )
    verify.run(results)
    assert "5: no description" in (results / "verification-report.md").read_text(encoding="utf-8")


# ---------- Sample images and archive ----------


def test_samples_are_twenty_images_of_different_products(tmp_path):
    products = [product(i, [1]) for i in range(1, 41)]
    (tmp_path / "products.jsonl").write_text("".join(json.dumps(p) + "\n" for p in products), encoding="utf-8")
    for p in products:
        write_jpeg(tmp_path / p["images"][0]["local_path"])

    assert publish.make_samples(tmp_path) == 0
    files = sorted(file.name for file in (tmp_path / "sample-images").glob("*.jpg"))
    assert len(files) == 20
    assert len({name.split("-")[0] for name in files}) == 20


def test_samples_are_the_same_for_the_same_seed_and_replace_the_old_ones(tmp_path):
    products = [product(i, [1]) for i in range(1, 41)]
    (tmp_path / "products.jsonl").write_text("".join(json.dumps(p) + "\n" for p in products), encoding="utf-8")
    for p in products:
        write_jpeg(tmp_path / p["images"][0]["local_path"])
    target = tmp_path / "sample-images"
    target.mkdir()
    (target / "old.jpg").write_bytes(b"x")

    publish.make_samples(tmp_path, seed=3)
    first = sorted(file.name for file in target.glob("*.jpg"))
    publish.make_samples(tmp_path, seed=3)
    assert sorted(file.name for file in target.glob("*.jpg")) == first
    assert "old.jpg" not in first


def test_fewer_products_than_requested_gives_fewer_samples(tmp_path):
    (tmp_path / "products.jsonl").write_text(json.dumps(product(1, [1])) + "\n", encoding="utf-8")
    write_jpeg(tmp_path / "images" / "1-1.jpg")
    assert publish.make_samples(tmp_path) == 0
    assert len(list((tmp_path / "sample-images").glob("*.jpg"))) == 1


def test_samples_without_images_is_an_error(tmp_path):
    (tmp_path / "products.jsonl").write_text(json.dumps({**product(1, [1]), "images": []}) + "\n", encoding="utf-8")
    assert publish.make_samples(tmp_path) == 1


def test_archive_holds_every_image_under_images(results):
    assert publish.make_archive(results) == 0
    with tarfile.open(results / config.IMAGES_ARCHIVE.name) as archive:
        names = sorted(archive.getnames())
    assert names == sorted(f"images/{file.name}" for file in (results / "images").glob("*.jpg"))
    assert not list(results.glob("*.part"))


def test_archive_over_the_limit_is_an_error_and_leaves_nothing(results, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_MAX_BYTES", 10)
    assert publish.make_archive(results) == 1
    assert not (results / config.IMAGES_ARCHIVE.name).exists()
    assert not list(results.glob("*.part"))


def test_archive_without_images_is_an_error(tmp_path):
    assert publish.make_archive(tmp_path) == 1


def test_commands_exist(capsys):
    with pytest.raises(SystemExit):
        main(["sample", "--seed", "x"])
    assert "--seed" in capsys.readouterr().err
