"""Check the finished results against the requirements of W2 and W3. No network.

`python -m scraper verify` prints one line per check, writes verification-report.md next to the results and
exits with 1 if any check failed. Run it after `crawl` and `images`.
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from . import config
from .crawl import load_json, load_lines
from .models import Category, Product

log = logging.getLogger(__name__)

# How many offenders a check lists before "..."
SHOWN = 5


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _some(items: list) -> str:
    shown = ", ".join(str(item) for item in items[:SHOWN])
    return shown + (f", ... ({len(items)} in total)" if len(items) > SHOWN else "")


def _read(results_dir: Path) -> tuple[list[Category], list[Product], list[str]]:
    """Categories and products validated against the schema, and one message per invalid record."""
    errors: list[str] = []
    categories, products = [], []
    for record in load_json(results_dir / config.CATEGORIES_FILE.name, []):
        try:
            categories.append(Category.model_validate(record))
        except ValidationError as exc:
            errors.append(f"category {record.get('id')}: {exc.error_count()} errors")
    for record in load_lines(results_dir / config.PRODUCTS_FILE.name):
        try:
            products.append(Product.model_validate(record))
        except ValidationError as exc:
            errors.append(f"product {record.get('id')}: {exc.error_count()} errors")
    return categories, products, errors


def _children(categories: list[Category]) -> dict[int | None, list[int]]:
    children = defaultdict(list)
    for category in categories:
        children[category.parent_id].append(category.id)
    return children


def _non_empty(categories: list[Category], products: list[Product]) -> set[int]:
    """Categories with a product in them or in a subcategory."""
    by_id = {category.id: category for category in categories}
    filled: set[int] = set()
    for product in products:
        for category_id in product.category_ids:
            while category_id in by_id and category_id not in filled:
                filled.add(category_id)
                parent = by_id[category_id].parent_id
                if parent is None:
                    break
                category_id = parent
    return filled


def check_records(categories: list[Category], products: list[Product], errors: list[str]) -> list[Check]:
    duplicate_ids = [pid for pid, n in Counter(p.id for p in products).items() if n > 1]
    duplicate_urls = [url for url, n in Counter(str(p.url) for p in products).items() if n > 1]
    return [
        Check(
            "No validation errors (schema)", not errors, f"{len(errors)} invalid: {_some(errors)}" if errors else "ok"
        ),
        Check(
            f"At least {config.MIN_PRODUCTS} products",
            len(products) >= config.MIN_PRODUCTS,
            f"{len(products)} products",
        ),
        Check(
            "No duplicate products",
            not duplicate_ids and not duplicate_urls,
            f"duplicate ids: {_some(duplicate_ids)}; urls: {_some(duplicate_urls)}"
            if duplicate_ids or duplicate_urls
            else "ok",
        ),
    ]


def check_categories(categories: list[Category], products: list[Product]) -> list[Check]:
    by_id = {category.id: category for category in categories}
    children = _children(categories)
    filled = _non_empty(categories, products)

    missing_parent = [c.id for c in categories if c.parent_id is not None and c.parent_id not in by_id]
    unknown_in_products = sorted({cid for p in products for cid in p.category_ids if cid not in by_id})
    empty = [f"{c.id} {c.name}" for c in categories if c.id not in filled]
    roots_ok = [
        by_id[root_id].name
        for root_id in children[None]
        if sum(1 for child in children[root_id] if child in filled) >= config.MIN_SUBCATEGORIES
    ]
    return [
        Check(
            f"At least {config.MIN_ROOT_CATEGORIES} categories with at least {config.MIN_SUBCATEGORIES} "
            "non-empty subcategories each",
            len(roots_ok) >= config.MIN_ROOT_CATEGORIES,
            f"{len(roots_ok)}: {', '.join(roots_ok)}",
        ),
        Check("No empty categories", not empty, f"{len(empty)} empty: {_some(empty)}" if empty else "ok"),
        Check(
            "Every parent and every product category exists",
            not missing_parent and not unknown_in_products,
            f"missing parents: {_some(missing_parent)}; unknown in products: {_some(unknown_in_products)}"
            if missing_parent or unknown_in_products
            else "ok",
        ),
    ]


def image_problem(path: Path) -> str | None:
    """Why the file at `path` breaks the image requirements, or None if it meets them."""
    size = path.stat().st_size
    if size > config.IMAGE_MAX_BYTES:
        return f"{path.name}: {size} bytes"
    try:
        with Image.open(path) as image:
            longer = max(image.size)
            if image.format != "JPEG":
                return f"{path.name}: {image.format}, not JPEG"
    except (UnidentifiedImageError, OSError) as exc:
        return f"{path.name}: unreadable ({exc})"
    if not config.IMAGE_MIN_SIDE <= longer <= config.IMAGE_MAX_SIDE:
        return f"{path.name}: longer side {longer} px"
    return None


def check_images(products: list[Product], results_dir: Path) -> list[Check]:
    without_image, two_images, missing_files, bad_files = [], 0, [], []
    referenced: set[str] = set()
    for product in products:
        present = 0
        for image in product.images:
            if not image.local_path:
                continue
            path = results_dir / image.local_path
            referenced.add(path.name)
            if not path.is_file():
                missing_files.append(image.local_path)
                continue
            present += 1
            problem = image_problem(path)
            if problem:
                bad_files.append(problem)
        if present == 0:
            without_image.append(product.id)
        if present >= 2:
            two_images += 1

    images_dir = results_dir / config.IMAGES_DIR.name
    on_disk = {file.name for file in images_dir.glob("*") if file.is_file()} if images_dir.is_dir() else set()
    orphans = sorted(on_disk - referenced)
    return [
        Check(
            "Every product has at least one image file",
            not without_image,
            f"{len(without_image)} without: {_some(without_image)}" if without_image else "ok",
        ),
        Check(
            f"At least {config.MIN_PRODUCTS_WITH_TWO_IMAGES} products have two or more images",
            two_images >= config.MIN_PRODUCTS_WITH_TWO_IMAGES,
            f"{two_images} products",
        ),
        Check(
            "Every image file listed in products.jsonl exists",
            not missing_files,
            f"{len(missing_files)} missing: {_some(missing_files)}" if missing_files else "ok",
        ),
        Check(
            f"Every image is JPEG, {config.IMAGE_MIN_SIDE}-{config.IMAGE_MAX_SIDE} px on the longer side, "
            f"at most {config.IMAGE_MAX_BYTES} bytes",
            not bad_files,
            f"{len(bad_files)} bad: {_some(bad_files)}" if bad_files else f"{len(on_disk)} files checked",
        ),
        Check(
            "No image file that no product uses",
            not orphans,
            f"{len(orphans)} unused: {_some(orphans)}" if orphans else "ok",
        ),
    ]


def check_files(results_dir: Path) -> list[Check]:
    """Result files are committed to git, except the images (see .gitignore)."""
    images_dir = results_dir / config.IMAGES_DIR.name
    archive = config.IMAGES_ARCHIVE.name
    big = [
        f"{file.name} ({file.stat().st_size} bytes)"
        for file in sorted(results_dir.rglob("*"))
        if file.is_file() and images_dir not in file.parents and file.name != archive
        if file.stat().st_size > config.MAX_RESULT_FILE_BYTES
    ]
    return [
        Check(
            f"No result file over {config.MAX_RESULT_FILE_BYTES // 1_000_000} MB",
            not big,
            f"too big: {_some(big)}" if big else "ok",
        )
    ]


def verify(results_dir: Path = config.RESULTS_DIR) -> list[Check]:
    categories, products, errors = _read(results_dir)
    return [
        *check_records(categories, products, errors),
        *check_categories(categories, products),
        *check_images(products, results_dir),
        *check_files(results_dir),
    ]


def rejected_summary(results_dir: Path) -> list[str]:
    rejected = load_json(results_dir / config.REJECTED_FILE.name, [])
    return [f"{entry['id']}: {entry['reason']}" for entry in rejected]


def write_report(path: Path, checks: list[Check], rejected: list[str]) -> None:
    lines = [
        "# Scraper results: verification report",
        "",
        f"Generated by `python -m scraper verify` on {date.today().isoformat()}.",
        "",
        "| Check | Result | Details |",
        "| --- | --- | --- |",
        *(f"| {c.name} | {'PASS' if c.ok else 'FAIL'} | {c.detail.replace('|', '/')} |" for c in checks),
        "",
        f"Products left out on purpose (`rejected.json`): {len(rejected)}",
        *(f"- {entry}" for entry in rejected),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(results_dir: Path = config.RESULTS_DIR) -> int:
    """Print the checks, write the report. Exit code 0 only if every check passed."""
    checks = verify(results_dir)
    for check in checks:
        print(f"{'PASS' if check.ok else 'FAIL'}  {check.name}: {check.detail}")
    write_report(results_dir / config.VERIFICATION_REPORT.name, checks, rejected_summary(results_dir))
    failed = [check for check in checks if not check.ok]
    print(f"\n{len(checks) - len(failed)} of {len(checks)} checks passed.")
    return 1 if failed else 0
