"""Parsers that turn pages and sitemaps of the source shop into records. They do not use the network."""

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import Category, validate_record

SITEMAP_NS = {"site": "http://www.sitemaps.org/schemas/sitemap/0.9"}
# Paths of product and category pages, e.g. /242-olejek-amla.html and /104-olejki-do-wlosow.
# ^ and $ make the pattern match the whole path, so /content/1-koszt-wysylki is not a category.
PRODUCT_PATH = re.compile(r"^/\d+-[^/]+\.html$")
# [^/.] does not allow a dot, so a product path (with .html) is never taken for a category.
CATEGORY_PATH = re.compile(r"^/\d+-[^/.]+$")


def name_from_soup(soup: BeautifulSoup) -> str:
    name = soup.select_one("h1.page-title-section")
    if name is None:
        raise ValueError("No category name (h1.page-title-section) on the page")
    return name.get_text(strip=True)


def id_from_url(url: str) -> int:
    parts = urlparse(url)
    path_parts = parts.path.split("-")
    category_id = path_parts[0].lstrip("/")
    if not category_id.isdigit():
        raise ValueError(f"Id can't be extracted from url: {url}")
    return int(category_id)


def parent_url_from_soup(soup: BeautifulSoup) -> str:
    for script in soup.select('script[type="application/ld+json"]'):
        data = json.loads(script.string)
        if data.get("@type") == "BreadcrumbList":
            bread_crumb_list = data["itemListElement"]
            if len(bread_crumb_list) < 2:
                raise ValueError("Breadcrumb has fewer than 2 items, so it has no parent")
            return bread_crumb_list[-2]["item"]
    raise ValueError("No BreadcrumbList JSON-LD on the page")


def parent_id_from_soup(soup: BeautifulSoup) -> int | None:
    url = parent_url_from_soup(soup)
    if urlparse(url).path == "/" or urlparse(url).path == "":
        return None
    return id_from_url(url)


def parse_category(url: str, html: str) -> Category | None:
    soup = BeautifulSoup(html, "html.parser")
    try:
        category_id = id_from_url(url)
        name = name_from_soup(soup)
        parent_id = parent_id_from_soup(soup)
    except ValueError as exc:
        raise ValueError(f"{url}: {exc}") from exc
    category_dict = {
        "id": category_id,
        "name": name,
        "url": url,
        "parent_id": parent_id,
    }
    category = validate_record(model=Category, data=category_dict, url=url)
    return category


def children_by_parent(categories: list[Category]) -> dict[int | None, list[Category]]:
    """Groups categories by the id of their parent. Top-level categories are under None."""
    groups: dict[int | None, list[Category]] = {}
    for category in categories:
        groups.setdefault(category.parent_id, []).append(category)
    return groups


def missing_parents(categories: list[Category]) -> list[Category]:
    """Categories whose parent is not in the list."""
    known_ids = {category.id for category in categories}
    known_ids.add(None)  # top-level categories have no parent to look for
    orphans = [category for category in categories if category.parent_id not in known_ids]
    return orphans


def parse_sitemap_index(xml: str) -> list[str]:
    """Addresses of the sitemaps listed in a sitemap index."""
    root = ET.fromstring(xml)
    sitemap = []
    for row in root.findall("site:sitemap/site:loc", SITEMAP_NS):
        sitemap.append(row.text)
    return sitemap


def parse_sitemap(xml: str) -> tuple[list[str], list[str]]:
    """Product and category addresses from a sitemap. Other addresses are skipped."""
    root = ET.fromstring(xml)
    products: list[str] = []
    categories: list[str] = []
    for row in root.findall("site:url/site:loc", SITEMAP_NS):
        url = row.text
        path = urlparse(url).path
        if PRODUCT_PATH.match(path):
            products.append(url)
        elif CATEGORY_PATH.match(path):
            categories.append(url)
    return products, categories
