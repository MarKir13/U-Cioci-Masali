"""The only module that talks to the shop: the PrestaShop Webservice API.

The importer runs on the Compose network and calls the shop directly over HTTP (http://shop/api/), the
way PR #79 set it up (shop/scripts/setup/webservice.php):
- the key is the HTTP Basic auth user, with an empty password. Never put it in the URL (?ws_key=),
  because URLs are written to the access log;
- `Host` must be the shop's own domain (localhost:<HTTPS_PORT>), or PrestaShop answers 302;
- `X-Forwarded-Proto: https` makes the request look the same as one that came through the proxy.

Reads ask for JSON (output_format=JSON). Writes are sent as XML, the format the API accepts.
"""

import itertools
import json
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Name of one record in the XML body, for each resource
SINGULAR = {
    "categories": "category",
    "manufacturers": "manufacturer",
    "products": "product",
    "specific_prices": "specific_price",
    "stock_availables": "stock_available",
}

PAGE_SIZE = 500


class ApiError(Exception):
    """The shop refused a request. `message` is PrestaShop's own explanation."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


class Lang(str):
    """A text field stored per language (name, description, link_rewrite): the same text for every language."""


def text(value: object) -> str:
    """A multilingual field as read back from the API: plain text with one language, a list with several."""
    if isinstance(value, list):
        return str(value[0]["value"]) if value else ""
    return "" if value is None else str(value)


def to_xml(resource: str, fields: dict, lang_ids: list[int]) -> bytes:
    """The XML body for creating or updating one record.

    `fields` maps field names to values. A Lang value becomes one <language id="..."> per language.
    The key "associations" maps a group to a list of (tag, {field: value}), for example
    {"categories": [("category", {"id": 12}), ...]}. ElementTree escapes &, < and > in the text.
    """
    root = ET.Element("prestashop")
    record = ET.SubElement(root, SINGULAR[resource])
    for name, value in fields.items():
        if name == "associations":
            associations = ET.SubElement(record, "associations")
            for group, items in value.items():
                group_node = ET.SubElement(associations, group)
                for tag, item in items:
                    item_node = ET.SubElement(group_node, tag)
                    for key, item_value in item.items():
                        ET.SubElement(item_node, key).text = str(item_value)
        elif isinstance(value, Lang):
            field = ET.SubElement(record, name)
            for lang_id in lang_ids:
                ET.SubElement(field, "language", id=str(lang_id)).text = str(value)
        else:
            ET.SubElement(record, name).text = "" if value is None else str(value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def error_message(response: requests.Response) -> str:
    """PrestaShop's error text from a JSON or XML error response."""
    body = response.text
    try:
        errors = json.loads(body).get("errors", [])
        return "; ".join(str(e.get("message", e)) for e in errors) or body[:300]
    except (ValueError, AttributeError):
        pass
    try:
        messages = [m.text or "" for m in ET.fromstring(body).iter("message")]
        return "; ".join(messages) or body[:300]
    except ET.ParseError:
        return body[:300] or response.reason


class ShopApi:
    def __init__(self, url: str, host: str, key: str, dry_run: bool = False, timeout: int = 300):
        self.url = url.rstrip("/")
        self.host = host
        self._key = key
        # --dry-run: read everything, write nothing. Created records get negative placeholder IDs.
        self.dry_run = dry_run
        self._placeholder_ids = itertools.count(-1, -1)
        self.timeout = timeout
        self.lang_ids: list[int] = [1]
        # requests.Session is not safe to share between threads, so each thread gets its own
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.auth = (self._key, "")
            session.headers.update({"Host": self.host, "X-Forwarded-Proto": "https"})
            # Retry only what is safe to repeat: a repeated POST could create a record twice
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[502, 503, 504],
                allowed_methods=["GET", "HEAD", "PUT", "DELETE"],
            )
            session.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=4))
            self._local.session = session
        return session

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        params = {"output_format": "JSON", **kwargs.pop("params", {})}
        response = self._session().request(
            method, f"{self.url}/{path}", params=params, timeout=self.timeout, allow_redirects=False, **kwargs
        )
        if response.status_code >= 300:
            raise ApiError(response.status_code, error_message(response))
        return response

    def check(self) -> None:
        """Fails early with a clear message if the API is off, the key is wrong or the Host is not the shop's."""
        self._request("GET", "languages", params={"display": "[id,iso_code]"})

    def load_languages(self) -> None:
        """Every installed language gets the same Polish text (the shop is Polish only)."""
        languages = self.list("languages", display="[id]")
        self.lang_ids = [int(language["id"]) for language in languages] or [1]

    def list(self, resource: str, display: str = "full", filters: dict | None = None) -> list[dict]:
        """All records of a resource, read in pages of PAGE_SIZE. `filters` maps a field to an exact value."""
        records: list[dict] = []
        params = {"display": display, "sort": "[id_ASC]"}
        for field, value in (filters or {}).items():
            params[f"filter[{field}]"] = f"[{value}]"
        while True:
            params["limit"] = f"{len(records)},{PAGE_SIZE}"
            body = self._request("GET", resource, params=params).json()
            # An empty result is [] instead of {"products": [...]}
            page = body.get(resource, []) if isinstance(body, dict) else []
            records.extend(page)
            if len(page) < PAGE_SIZE:
                return records

    def get(self, resource: str, record_id: int) -> dict:
        return self._request("GET", f"{resource}/{record_id}").json()[SINGULAR[resource]]

    def create(self, resource: str, fields: dict) -> dict:
        body = to_xml(resource, fields, self.lang_ids)
        if self.dry_run:
            return {"id": next(self._placeholder_ids)}
        return self._request("POST", resource, data=body).json()[SINGULAR[resource]]

    def update(self, resource: str, record_id: int, fields: dict) -> None:
        """Replaces the record: PrestaShop empties every field that `fields` leaves out."""
        body = to_xml(resource, {"id": record_id, **fields}, self.lang_ids)
        if not self.dry_run:
            self._request("PUT", f"{resource}/{record_id}", data=body)

    def delete(self, resource: str, record_id: int) -> None:
        if not self.dry_run:
            self._request("DELETE", f"{resource}/{record_id}")

    def upload_image(self, product_id: int, path: Path) -> None:
        """Adds an image to a product. PrestaShop makes it the cover if the product has none yet."""
        if self.dry_run:
            return
        with path.open("rb") as file:
            files = {"image": (path.name, file, "image/jpeg")}
            self._request("POST", f"images/products/{product_id}", files=files)

    def delete_image(self, product_id: int, image_id: int) -> None:
        if not self.dry_run:
            self._request("DELETE", f"images/products/{product_id}/{image_id}")
