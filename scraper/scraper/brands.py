"""Brand pages: products.jsonl brands -> brand index -> each brand's page -> brands.json. Can be stopped and resumed.

Why the data is kept as it is: docs/adr/0014-brand-pages.md

The scraper keeps only the brand name of each product. The source shows more on a brand page (`/brand/<id>-<slug>`):
an H1, an intro, sections and an FAQ, which the shop imports into its manufacturers. The brand index
(/producenci) gives the page address of each brand; a brand of our products that is not on the index has no page.
Such a brand is saved with its name only and reported, since the importer still needs to know it exists.

brands.json is written again after every brand (see `save_json`), so Ctrl+C at any moment leaves it readable. On
the next run the brands already in it are skipped, so they are not downloaded again.
"""

import json
import logging
from collections import Counter
from pathlib import Path

import requests

from . import config
from .crawl import PageCache, load_lines, save_json
from .http_client import HttpClient, SkippedURL
from .models import Brand, validate_record
from .parsers import brand_key, parse_brand, parse_brand_index

log = logging.getLogger(__name__)


def brand_names(products_file: Path) -> list[str]:
    """The brands of the saved products, once each (the first spelling), in alphabetical order."""
    names: dict[str, str] = {}
    for product in load_lines(products_file):
        name = product.get("brand")
        if name:
            names.setdefault(brand_key(name), name)
    return sorted(names.values(), key=brand_key)


class BrandCrawler:
    def __init__(
        self,
        client: HttpClient,
        results_dir: Path = config.RESULTS_DIR,
        cache: PageCache | None = None,
        limit: int | None = None,
    ):
        self.client = client
        self.cache = cache
        self.limit = limit  # test runs: at most `limit` new brand pages
        self.products_file = results_dir / config.PRODUCTS_FILE.name
        self.brands_file = results_dir / config.BRANDS_FILE.name

    def run(self) -> int:
        """Returns the exit code for the command line: 0, 1 if a brand failed, 130 if interrupted."""
        try:
            return self._run()
        except KeyboardInterrupt:
            log.warning("Interrupted. Everything saved so far is kept; run the same command to resume.")
            return 130

    def _run(self) -> int:
        names = brand_names(self.products_file)
        if not names:
            log.error("No brands found in %s: run the crawl first", self.products_file)
            return 1
        saved: dict[str, dict] = {brand_key(b["name"]): b for b in self.load_saved()}
        todo = [name for name in names if brand_key(name) not in saved]
        log.info(
            "Brands: %d in the products, %d already saved, %d to do", len(names), len(names) - len(todo), len(todo)
        )
        stats = Counter(saved=0)
        stats["already saved"] = len(names) - len(todo)
        if todo:
            try:
                self.client.load_robots()
            except requests.RequestException as exc:
                log.error("Could not read robots.txt, stopping: %s", exc)
                return 1
            index = self.read_index()
            if index is None:
                return 1
            for name in todo:
                if self.limit is not None and stats["downloaded"] >= self.limit:
                    break
                brand = self.brand(name, index, stats)
                if brand is not None:
                    saved[brand_key(name)] = brand.model_dump(mode="json")
                    save_json(self.brands_file, sorted(saved.values(), key=lambda b: brand_key(b["name"])))
        self.report(saved, stats)
        return 1 if stats["failed"] else 0

    def load_saved(self) -> list[dict]:
        if not self.brands_file.exists():
            return []
        return json.loads(self.brands_file.read_text(encoding="utf-8"))

    def read_index(self) -> dict[str, tuple[str, str]] | None:
        url = config.BASE_URL + config.BRAND_INDEX
        html = self.fetch(url)
        if html is None:
            log.error("Could not read the brand index %s, stopping", url)
            return None
        index = parse_brand_index(url, html)
        log.info("Brand index: %d brand pages", len(index))
        return index

    def brand(self, name: str, index: dict[str, tuple[str, str]], stats: Counter) -> Brand | None:
        """The record to save for `name`, or None if its page could not be downloaded or parsed (logged)."""
        page = index.get(brand_key(name))
        if page is None:
            log.warning("Brand %r has no page in the source shop, saved with its name only", name)
            stats["no page"] += 1
            stats["saved"] += 1
            return validate_record(Brand, {"name": name}, name)
        url = page[1]
        stats["downloaded"] += 1
        html = self.fetch(url)
        if html is None:
            stats["failed"] += 1
            return None
        try:
            brand = parse_brand(name, url, html)
        except ValueError as exc:
            log.error("Could not parse brand page %s: %s", url, exc)
            brand = None
        if brand is None:  # parse error above, or invalid record (logged by validate_record)
            stats["failed"] += 1
            return None
        stats["saved"] += 1
        if not brand.description:
            log.info("Brand %r: the page has no description", name)
            stats["no description"] += 1
        return brand

    def fetch(self, url: str) -> str | None:
        """Text of the page at `url`, from the cache or the shop. None if it failed (the reason is logged)."""
        if self.cache is not None:
            cached = self.cache.get(url)
            if cached is not None:
                log.debug("From cache: %s", url)
                return cached
        try:
            text = self.client.get(url).text
        except SkippedURL:  # robots.txt or outside the shop, already logged by the client
            return None
        except requests.RequestException as exc:
            log.error("Could not download %s: %s", url, exc)
            return None
        if self.cache is not None:
            self.cache.put(url, text)
        return text

    @staticmethod
    def report(saved: dict[str, dict], stats: Counter) -> None:
        without_page = sorted(b["name"] for b in saved.values() if not b["url"])
        without_text = sorted(b["name"] for b in saved.values() if b["url"] and not b["description"])
        log.info(
            "Brands: %d saved now, %d already saved, %d failed; %d in %s",
            stats["saved"],
            stats["already saved"],
            stats["failed"],
            len(saved),
            config.BRANDS_FILE.name,
        )
        if without_page:
            log.warning("Brands without a page in the source shop (%d): %s", len(without_page), ", ".join(without_page))
        if without_text:
            log.info("Brands whose page has no description (%d): %s", len(without_text), ", ".join(without_text))
