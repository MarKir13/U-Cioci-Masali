"""Web scraping data functions using BeautifulSoup"""
import json
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import Category, validate_record


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
            return bread_crumb_list[-2]["item"]
    raise ValueError("No BreadcrumbList JSON-LD on the page")


def parent_id_from_soup(soup: BeautifulSoup) -> int | None:
    url = parent_url_from_soup(soup)
    if urlparse(url).path == "/" or urlparse(url).path == "":
        return None
    return id_from_url(url)


def parse_category(url: str, html: str) -> Category | None:
    soup = BeautifulSoup(html, "html.parser")
    category_id = id_from_url(url)
    name = name_from_soup(soup)
    parent_id = parent_id_from_soup(soup)
    category_dict = {
        "id": category_id,
        "name": name,
        "url": url,
        "parent_id": parent_id,
    }
    category = validate_record(model=Category, data=category_dict, url=url)
    return category

