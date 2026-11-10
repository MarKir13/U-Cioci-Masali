"""Parsers that turn pages and sitemaps of the source shop into records. They do not use the network."""

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Category, Product, validate_record

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


def product_urls(url: str, html: str) -> list[str]:
    """Extract absolute, unique product URLs from a product list page."""
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a_tag in soup.select('#js-product-list article.product-miniature a[href$=".html"]'):
        href = a_tag.get("href")
        if href:
            absolute = urljoin(url, href)
            if absolute not in urls:
                urls.append(absolute)
    return urls


def next_page_url(url: str, html: str) -> str | None:
    """Extract the URL of the next page from the pagination button, or return None if it's the last page."""
    soup = BeautifulSoup(html, "html.parser")

    next_button = soup.select_one("button.next")

    if not next_button or "disabled" in next_button.get("class", []):
        return None

    href = next_button.get("data-ps-data")
    if href:
        return urljoin(url, href)

    return None


def parse_product(url: str, html: str) -> Product | None:
    """Extracts product data from data-product, JSON-LD, and HTML to build a validated Product."""
    soup = BeautifulSoup(html, "html.parser")

    details_div = soup.select_one("div.js-product-details")
    if not details_div or not details_div.has_attr("data-product"):
        raise ValueError("Missing data-product attribute on div.js-product-details")

    try:
        data = json.loads(details_div["data-product"])
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON in data-product") from exc

    regular_price = data.get("price_without_reduction")
    if regular_price is not None:
        regular_price = round(float(regular_price), 2)

    images = []
    for img in data.get("images", []):
        try:
            images.append({"source_url": img["bySize"]["product_main_2x"]["url"]})
        except KeyError:
            continue

    product_dict = {
        "id": data.get("id"),
        "url": url,
        "name": data.get("name"),
        "description": data.get("description"),
        "price": data.get("price_amount"),
        "regular_price": regular_price,
        "has_discount": bool(data.get("has_discount")),
        "vat_rate": data.get("rate"),
        "images": images,
        "category_ids": [data.get("id_category_default")] if data.get("id_category_default") else [],
        "family": [],
    }

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            ld_data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        if ld_data.get("@type") == "Product":
            product_dict["size"] = ld_data.get("size")
            product_dict["color"] = ld_data.get("color")
            product_dict["material"] = ld_data.get("material")
            product_dict["pattern"] = ld_data.get("pattern")

            weight = ld_data.get("weight", {})
            if isinstance(weight, dict) and weight.get("value"):
                product_dict["weight"] = {"value": weight.get("value"), "unit": weight.get("unitCode", "")}

            brand = ld_data.get("brand", {})
            product_dict["brand"] = brand.get("name") if isinstance(brand, dict) else brand
            product_dict["ean"] = ld_data.get("gtin")

        elif ld_data.get("@type") == "BreadcrumbList":
            for item in ld_data.get("itemListElement", []):
                item_url = item.get("item")
                if item_url:
                    try:
                        cat_id = id_from_url(item_url)
                        if cat_id not in product_dict["category_ids"]:
                            product_dict["category_ids"].append(cat_id)
                    except ValueError:
                        pass

    for variant_link in soup.select("nav.ndx-family .ndx-family__opt"):
        href = variant_link.get("href")
        if href and href not in product_dict["family"]:
            product_dict["family"].append(href)

    return validate_record(model=Product, data=product_dict, url=url)
