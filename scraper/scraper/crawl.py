"""Full scraper run: sitemap -> categories -> listings -> products. Can be stopped and resumed.

Why the data comes from where it does: docs/adr/0004-crawl-sources-and-category-assignment.md

Results in scraper-results/:
- categories.json: every category, rewritten after each new one;
- listings.json: product URLs found on each category listing, and the next page to walk;
- products.jsonl: one product per line, appended as soon as it is parsed.

Each file is written so that Ctrl+C at any moment leaves it readable (see `save_json` and `append_line`).
On the next run everything already saved is loaded and skipped, so it is not downloaded again.
"""

import gzip
import hashlib
import json
import logging
import os
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag

import requests

from . import config
from .http_client import HttpClient, SkippedURL
from .models import Product, validate_record
from .parsers import (
    id_from_url,
    next_page_url,
    parse_category,
    parse_product,
    parse_sitemap,
    parse_sitemap_index,
    product_urls,
)

log = logging.getLogger(__name__)


# ---------- Saving and loading results ----------


def save_json(path: Path, data) -> None:
    """Write `data` to a temporary file, then rename it over `path`.

    The rename replaces the file in one step, so an interrupted run leaves either the old or the new
    version, never half of one.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_line(path: Path, record: dict) -> None:
    """Append one record as a JSON line, written in a single call and flushed at once."""
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as file:
        file.write(line)


def load_lines(path: Path) -> list[dict]:
    """Records from a JSON Lines file.

    A last line without "\\n" was cut off by an interruption: it is removed from the file and
    downloaded again. A broken line anywhere else is not ours to guess about, so it raises ValueError.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    # After the last "\n" there is either nothing or the cut-off line
    if lines[-1]:
        log.warning("Removing an incomplete last line from %s (the previous run was interrupted)", path.name)
        path.write_text("".join(line + "\n" for line in lines[:-1]), encoding="utf-8")
    records = []
    for number, line in enumerate(lines[:-1], start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} line {number} is not valid JSON: {exc}") from exc
    return records


@dataclass
class Listing:
    """What one category listing showed so far. `next_page` is None once the last page is done."""

    products: list[str] = field(default_factory=list)
    next_page: str | None = None


def load_listings(path: Path) -> dict[int, Listing]:
    data = load_json(path, {})
    # JSON object keys are always strings, so the ids are turned back into numbers
    return {int(category_id): Listing(**listing) for category_id, listing in data.items()}


def save_listings(path: Path, listings: dict[int, Listing]) -> None:
    save_json(path, {str(category_id): vars(listing) for category_id, listing in listings.items()})


class PageCache:
    """Downloaded pages on disk (gzipped), so a parser fix can be re-run without downloading again."""

    def __init__(self, directory: Path):
        self.directory = directory

    def _path(self, url: str) -> Path:
        # URLs contain characters that are not allowed in file names, so the file is named by a hash
        return self.directory / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".html.gz")

    def get(self, url: str) -> str | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            return gzip.decompress(path.read_bytes()).decode("utf-8")
        except (OSError, EOFError, UnicodeDecodeError):
            log.warning("Ignoring a damaged cache file for %s", url)
            return None

    def put(self, url: str, text: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(url)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(gzip.compress(text.encode("utf-8")))
        os.replace(tmp, path)


# ---------- The run ----------


class Crawler:
    def __init__(
        self,
        client: HttpClient,
        results_dir: Path = config.RESULTS_DIR,
        cache: PageCache | None = None,
        limit: int | None = None,
        full_listing_ids: tuple[int, ...] = config.FULL_LISTING_CATEGORY_IDS,
    ):
        self.client = client
        self.cache = cache
        # Test runs: at most `limit` new pages in each stage (categories, listing pages, products)
        self.limit = limit
        self.full_listing_ids = full_listing_ids
        self.categories_file = results_dir / config.CATEGORIES_FILE.name
        self.listings_file = results_dir / config.LISTINGS_FILE.name
        self.products_file = results_dir / config.PRODUCTS_FILE.name
        results_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> int:
        """Run every stage. Returns the exit code for the command line."""
        try:
            return self._run()
        except KeyboardInterrupt:
            log.warning("Interrupted. Everything saved so far is kept; run the same command to resume.")
            return 130

    def _run(self) -> int:
        # robots.txt is loaded once, before any loop. If that fails the run stops here: the per-URL error
        # handling below would otherwise try to download it again for every single URL.
        try:
            self.client.load_robots()
        except requests.RequestException as exc:
            log.error("Could not read robots.txt, stopping: %s", exc)
            return 1

        urls = self.read_sitemaps()
        if urls is None:
            return 1
        product_page_urls, category_page_urls = urls

        categories = {category["id"]: category for category in load_json(self.categories_file, [])}
        listings = load_listings(self.listings_file)
        self.crawl_categories(category_page_urls, categories, listings)
        self.walk_full_listings(listings)

        # Keyed by the id in the URL, the same key crawl_products uses to decide what to skip
        products = {id_from_url(record["url"]): record for record in load_lines(self.products_file)}
        self.crawl_products(product_page_urls, listings, products)

        self.report(categories, listings, products)
        return 0

    def read_sitemaps(self) -> tuple[list[str], list[str]] | None:
        """(product URLs, category URLs) from the sitemap, or None if it cannot be read.

        Always downloaded fresh (2 requests), so new products in the shop are picked up on resume.
        """
        products: list[str] = []
        categories: list[str] = []
        try:
            for sitemap_url in parse_sitemap_index(self.client.get(config.SITEMAP_INDEX).text):
                found_products, found_categories = parse_sitemap(self.client.get(sitemap_url).text)
                products += found_products
                categories += found_categories
        # Without the sitemap there is nothing to crawl. ET.ParseError (broken XML) is not a ValueError.
        except (SkippedURL, requests.RequestException, ValueError, ET.ParseError) as exc:
            log.error("Could not read the sitemap, stopping: %s", exc)
            return None
        log.info("Sitemap: %d product and %d category URLs", len(products), len(categories))
        return products, categories

    def crawl_categories(self, urls: list[str], categories: dict[int, dict], listings: dict[int, Listing]) -> None:
        """Save each category. Its page is also page 1 of its listing, so those products are saved too."""
        stats = Counter()
        for url in urls:
            category_id = id_from_url(url)
            if category_id in categories:
                stats["already saved"] += 1
                continue
            if self._limit_reached(stats["downloaded"]):
                break
            stats["downloaded"] += 1

            html = self.fetch(url)
            if html is None:
                stats["failed"] += 1
                continue
            try:
                category = parse_category(url, html)
                listing = Listing(products=product_urls(url, html), next_page=next_page_url(url, html))
            except ValueError as exc:
                log.error("Could not parse category %s: %s", url, exc)
                category = None
            if category is None:  # parse error above, or invalid record (logged by validate_record)
                stats["failed"] += 1
                continue

            # The listing goes first: if the run stops between the two writes, the category is not saved
            # yet, so its page is downloaded again next time and the listing is written again.
            listings[category.id] = listing
            save_listings(self.listings_file, listings)
            categories[category.id] = category.model_dump(mode="json")
            save_json(self.categories_file, list(categories.values()))
            stats["saved"] += 1
        self._log_stats("Categories", stats)

    def walk_full_listings(self, listings: dict[int, Listing]) -> None:
        """Walk Na prezent and Nowości to their last page, saving after every page.

        Other categories keep only page 1 (see the ADR). A listing whose `next_page` is None is finished
        and is not downloaded again.
        """
        stats = Counter()
        for category_id in self.full_listing_ids:
            listing = listings.get(category_id)
            if listing is None:
                log.error("Category %d was not saved, so its listing cannot be walked", category_id)
                continue
            while listing.next_page:
                if self._limit_reached(stats["downloaded"]):
                    break
                stats["downloaded"] += 1
                page_url = listing.next_page

                html = self.fetch(page_url)
                if html is None:
                    # next_page stays as it is, so the next run tries this page again
                    log.error("Listing of category %d stopped at %s", category_id, page_url)
                    stats["failed"] += 1
                    break
                for product_url in product_urls(page_url, html):
                    if product_url not in listing.products:
                        listing.products.append(product_url)
                next_url = next_page_url(page_url, html)
                # A "next" button pointing at the same page would loop forever
                listing.next_page = next_url if next_url != page_url else None
                save_listings(self.listings_file, listings)
                stats["saved"] += 1
            log.info("Listing of category %d: %d products", category_id, len(listing.products))
        self._log_stats("Listing pages", stats)

    def crawl_products(self, sitemap_urls: list[str], listings: dict[int, Listing], products: dict[int, dict]) -> None:
        """Download and save every product from the sitemap and the listings, merging its categories."""
        # One URL per product id: the sitemap URL first, then products seen only on a listing.
        # Ids, not URLs, decide what is the same product, because one product can have several URLs.
        urls: dict[int, str] = {}
        for url in sitemap_urls:
            urls.setdefault(id_from_url(url), url)
        # Categories each product was seen in on a listing
        listed_in: dict[int, list[int]] = {}
        for category_id, listing in listings.items():
            for url in listing.products:
                product_id = id_from_url(url)
                urls.setdefault(product_id, urldefrag(url).url)
                listed_in.setdefault(product_id, [])
                if category_id not in listed_in[product_id]:
                    listed_in[product_id].append(category_id)

        stats = Counter()
        skipped = [product_id for product_id in urls if product_id in products]
        if skipped:
            log.info("Skipping %d products already saved in %s", len(skipped), self.products_file.name)
        stats["already saved"] = len(skipped)

        for product_id, url in urls.items():
            if product_id in products:
                continue
            if self._limit_reached(stats["downloaded"]):
                break
            stats["downloaded"] += 1

            product = self.product_from_page(url, listed_in.get(product_id, []))
            if product is None:
                stats["failed"] += 1
                continue
            if product.id != product_id:
                log.warning("Product %s has id %d in its data, not %d as in its URL", url, product.id, product_id)
            record = product.model_dump(mode="json")
            append_line(self.products_file, record)
            products[product_id] = record
            stats["saved"] += 1
        self._log_stats("Products", stats)

    def product_from_page(self, url: str, listed_in: list[int]) -> Product | None:
        """The product on `url` with the listing categories added, or None (the reason is logged)."""
        html = self.fetch(url)
        if html is None:
            return None
        try:
            product = parse_product(url, html)
        except ValueError as exc:
            log.error("Could not parse product %s: %s", url, exc)
            return None
        if product is None:  # invalid record, logged by validate_record
            return None

        # The page gives the default category and its breadcrumb; listings add the rest (Na prezent, Nowości)
        extra = [category_id for category_id in listed_in if category_id not in product.category_ids]
        if not extra:
            return product
        # Validated again, so a merged record follows the same rules as a parsed one
        data = product.model_dump(mode="json")
        data["category_ids"] = product.category_ids + extra
        return validate_record(model=Product, data=data, url=url)

    def report(self, categories: dict[int, dict], listings: dict[int, Listing], products: dict[int, dict]) -> None:
        """Warn about categories that would be empty in our shop, and about unknown category ids."""
        used = {category_id for product in products.values() for category_id in product["category_ids"]}
        for category_id, category in categories.items():
            listing = listings.get(category_id)
            if listing and listing.products and category_id not in used:
                name = category["name"]
                log.warning("Category %d %s has products in the source shop but none saved", category_id, name)
        unknown = sorted(used - categories.keys())
        if unknown:
            log.warning("Products refer to categories that were not saved: %s", unknown)
        log.info("Saved %d categories and %d products in %s", len(categories), len(products), self.products_file.parent)

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

    def _limit_reached(self, downloaded: int) -> bool:
        return self.limit is not None and downloaded >= self.limit

    @staticmethod
    def _log_stats(stage: str, stats: Counter) -> None:
        log.info(
            "%s: %d saved, %d already saved, %d failed",
            stage,
            stats["saved"],
            stats["already saved"],
            stats["failed"],
        )
