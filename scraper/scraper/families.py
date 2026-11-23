"""Family blocks of the product pages: the rows of tiles that link a product to its siblings (issue #114).

On the source a product page shows its family above the description, made by the shop's own module
`ndx-family`. Each row has a title ("Mydło", "Pojemność") and one option per sibling: a photo tile with a
short label ("100% oliwa"), or a text button ("200 ml"). The current product's option is a <span>, not a link.

`products.jsonl` keeps only the sibling URLs (`family`). This file adds the titles and labels, read from the
page cache only (never the network), and writes `families.json`: product id -> list of rows.
"""

import json
import logging
import os
import shutil
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from . import config
from .crawl import PageCache, load_lines
from .models import FamilyAxis, ProductFamily, validate_record
from .parsers import id_from_url, product_data

log = logging.getLogger(__name__)


def parse_family(url: str, html: str) -> ProductFamily | None:
    """The family block of a product page, or None if the page has none (or it is invalid, which is logged)."""
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one("nav.ndx-family")
    if nav is None:
        return None
    product_id = product_data(url, soup).get("id")
    axes = []
    for axis in nav.select(".ndx-family__axis"):
        legend = axis.select_one(".ndx-family__legend")
        options = []
        for option in axis.select(".ndx-family__opt"):
            href = option.get("href")
            # The current product is a <span> without a link
            source_id = id_from_url(href) if href else product_id
            # A photo tile has its label in .ndx-family__cap; a text button is only the label
            caption = option.select_one(".ndx-family__cap")
            label = (caption or option).get_text(" ", strip=True)
            options.append({"source_id": source_id, "label": label})
        axes.append(
            {
                "title": legend.get_text(strip=True) if legend else None,
                "kind": "text" if "ndx-family__axis--text" in axis.get("class", []) else "image",
                "options": options,
            }
        )
    return validate_record(ProductFamily, {"product_id": product_id, "axes": axes}, url)


def save_families(path: Path, families: dict[int, list[FamilyAxis]]) -> None:
    """One product per line, so a change shows up in a diff as the lines of the products it touches."""
    lines = [
        f'"{product_id}": ' + json.dumps([axis.model_dump(mode="json") for axis in axes], ensure_ascii=False)
        for product_id, axes in sorted(families.items())
    ]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")
    os.replace(tmp, path)


def build_families(
    products_file: Path = config.PRODUCTS_FILE,
    cache: PageCache | None = None,
    out_file: Path = config.FAMILIES_FILE,
    shop_copy: Path | None = config.SHOP_FAMILIES_FILE,
) -> int:
    """Writes `families.json` for the saved products that have a family, from their pages in the cache.

    Never uses the network. If any page is missing from the cache, nothing is written (the files stay as they
    are) and the exit code is 1. A block that fails validation is logged and left out, and the exit code is
    then 1 as well. The file is also copied into the shop module (`shop_copy`), if its
    folder exists: in the Compose service `scraper` only scraper-results/ is mounted, so copy it by hand there.
    """
    cache = cache or PageCache(config.CACHE_DIR)
    stats = Counter()
    families: dict[int, list[FamilyAxis]] = {}
    for record in load_lines(products_file):
        if not record.get("family"):
            continue
        html = cache.get(record["url"])
        if html is None:
            log.warning("Product %d: page not in the cache, family skipped: %s", record["id"], record["url"])
            stats["not in the cache"] += 1
            continue
        try:
            family = parse_family(record["url"], html)
        except ValueError as exc:
            log.error("Product %d: %s", record["id"], exc)
            family = None
        if family is None:
            stats["failed"] += 1
            continue
        families[family.product_id] = family.axes
    if stats["not in the cache"]:
        # scraper/cache/ is gitignored: on a clean clone every page is missing, and writing would empty the data
        log.error("%d pages not in the cache: %s left unchanged", stats["not in the cache"], out_file)
        return 1
    save_families(out_file, families)
    log.info(
        "Families: %d products saved to %s, %d not in the cache, %d failed",
        len(families),
        out_file,
        stats["not in the cache"],
        stats["failed"],
    )
    if shop_copy is not None:
        if shop_copy.parent.is_dir():
            shutil.copyfile(out_file, shop_copy)
            log.info("Copied to %s", shop_copy)
        else:
            log.warning("%s not found: copy %s there by hand", shop_copy.parent, out_file.name)
    return 1 if stats["not in the cache"] or stats["failed"] else 0
