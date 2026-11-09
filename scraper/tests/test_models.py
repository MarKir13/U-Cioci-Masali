"""Tests for the scraped data models and for logging invalid records."""

import json
import logging
import re
from decimal import Decimal

import pytest
from pydantic import ValidationError

from scraper import config
from scraper.__main__ import main
from scraper.logging_config import setup_logging
from scraper.models import Category, Product, json_schema, validate_record

PRODUCT_URL = "https://www.magiczne-indie.pl/5425-bio-amalaki.html"
FAMILY_URL = "https://www.magiczne-indie.pl/706-olejek.html"
IMAGE_URL = "https://www.magiczne-indie.pl/14452-product_main_2x/amalaki.jpg"

""" ========== HELPER FUNCTIONS =========="""


def category_data(**changes) -> dict:
    data = {"id": 104, "name": "Olejki do włosów", "url": "https://www.magiczne-indie.pl/104-olejki", "parent_id": 38}
    return data | changes


def product_data(**changes) -> dict:
    """A product shaped like `product_discounted.html`, with only the required fields."""
    data = {
        "id": 5425,
        "url": PRODUCT_URL,
        "name": "Amalaki 60 kapsułek",
        "description": "<p>Główne źródło witaminy C</p>",
        "price": 64.72,
        "regular_price": 69.59,
        "has_discount": True,
        "category_ids": [385],
        "images": [{"source_url": "https://www.magiczne-indie.pl/14452-product_main_2x/amalaki.jpg"}],
    }
    return data | changes


def without(data: dict, field: str) -> dict:
    return {key: value for key, value in data.items() if key != field}


@pytest.fixture
def log_file(tmp_path):
    """Log the way a real run does, but to a temporary file. Undoes the changes to the root logger afterwards."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    path = tmp_path / "scraper.log"
    setup_logging(path)
    yield path
    for handler in root.handlers:
        handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


""" ========== VALID RECORDS =========="""


def test_minimal_product_leaves_optional_fields_empty():
    product = Product.model_validate(product_data())
    assert product.price == Decimal("64.72")
    assert product.regular_price == Decimal("69.59")
    assert product.vat_rate is None
    assert product.brand is None
    assert product.weight is None
    assert product.family == []
    assert product.images[0].local_path is None


def test_product_with_all_fields():
    product = Product.model_validate(
        product_data(
            vat_rate=23,
            brand="Dabur",
            ean="5022496101349",
            size="200 ml",
            color="złoty",
            material="szkło",
            pattern="Amla",
            weight={"value": "250.000000", "unit": "g"},
            family=["https://www.magiczne-indie.pl/706-olejek.html"],
        )
    )
    assert product.vat_rate == 23
    assert product.ean == "5022496101349"
    assert product.pattern == "Amla"
    assert str(product.family[0]) == "https://www.magiczne-indie.pl/706-olejek.html"


def test_raw_weight_is_kept_exactly_as_on_the_page():
    product = Product.model_validate(product_data(weight={"value": "1.187000", "unit": "g"}))
    assert product.weight.value == "1.187000"
    assert product.weight.unit == "g"


@pytest.mark.parametrize("value", ["", "   ", None])
def test_blank_optional_text_becomes_none(value):
    """A blank optional field must not cost us the whole product."""
    assert Product.model_validate(product_data(brand=value, ean=value)).brand is None


def test_top_level_category_has_no_parent():
    assert Category.model_validate(category_data(id=8, parent_id=None)).parent_id is None


def test_saved_product_reads_back_unchanged():
    """Resuming a run reads products.jsonl, so a saved line has to load back into the same record."""
    product = Product.model_validate(product_data(weight={"value": "250.000000", "unit": "g"}))
    line = product.model_dump_json()
    assert "Amalaki 60 kapsułek" in line  # UTF-8, not \u escapes
    assert json.loads(line)["url"] == PRODUCT_URL  # the same string the sitemap gives
    assert Product.model_validate_json(line) == product


@pytest.mark.parametrize(
    ("price", "regular_price", "has_discount"),
    [
        ("64.72", "69.59", True),
        ("272.99", "272.99", False),  # equal prices are the normal case for a product without a discount
        ("10.00", "10", False),  # equal once normalized
        # The flag comes from the page. #9 forbids deriving it from the prices, so no combination is rejected.
        ("64.72", "69.59", False),
        ("272.99", "272.99", True),
    ],
)
def test_price_up_to_regular_price_is_accepted_and_the_flag_is_not_derived(price, regular_price, has_discount):
    product = Product.model_validate(product_data(price=price, regular_price=regular_price, has_discount=has_discount))
    assert product.has_discount is has_discount


def test_lists_without_duplicates_are_accepted_in_their_original_order():
    second_image = "https://www.magiczne-indie.pl/14453-product_main_2x/amalaki.jpg"
    product = Product.model_validate(
        product_data(
            category_ids=[458, 385],
            family=[FAMILY_URL, PRODUCT_URL],
            images=[{"source_url": IMAGE_URL}, {"source_url": second_image}],
        )
    )
    assert product.category_ids == [458, 385]
    assert [str(url) for url in product.family] == [FAMILY_URL, PRODUCT_URL]
    assert [str(image.source_url) for image in product.images] == [IMAGE_URL, second_image]


""" ========== INVALID RECORDS =========="""


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"price": 0}, "price"),
        ({"price": -1}, "price"),
        ({"price": float("nan")}, "price"),
        ({"price": float("inf")}, "price"),
        ({"regular_price": 0}, "regular_price"),
        ({"regular_price": 69.58764}, "regular_price"),  # raw value from data-product, not rounded
        ({"price": "64.725000"}, "price"),  # zeros at the end do not hide a third decimal place
        ({"price": "1e-3"}, "price"),
        ({"regular_price": "10000000000.00"}, "regular_price"),  # one digit over the limit
        ({"regular_price": "1e30"}, "regular_price"),
        ({"regular_price": "12345678901234567890123456789.12"}, "regular_price"),  # normalize() would round it
        ({"regular_price": "1e1000000"}, "regular_price"),  # normalize() would raise Overflow and stop the run
        ({"category_ids": [385, 385]}, "category_ids"),
        ({"category_ids": [385, "385"]}, "category_ids"),  # the same id once parsed
        ({"family": [FAMILY_URL, FAMILY_URL]}, "family"),
        ({"family": [FAMILY_URL, FAMILY_URL.replace("www", "WWW")]}, "family"),  # the same URL once parsed
        ({"images": [{"source_url": IMAGE_URL}, {"source_url": IMAGE_URL}]}, "images"),
        ({"images": [{"source_url": IMAGE_URL}, {"source_url": IMAGE_URL, "local_path": "a.jpg"}]}, "images"),
        ({"url": "not-a-url"}, "url"),
        ({"url": "ftp://www.magiczne-indie.pl/x"}, "url"),
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"description": ""}, "description"),
        ({"description": "  \n "}, "description"),
        ({"description": "<p></p>"}, "description"),
        ({"description": "<p>&nbsp;</p>\n<br />"}, "description"),
        ({"images": []}, "images"),
        ({"images": [{"source_url": "not-a-url"}]}, "images"),
        ({"category_ids": []}, "category_ids"),
        ({"vat_rate": -1}, "vat_rate"),
        ({"vat_rate": 101}, "vat_rate"),
        ({"family": ["not-a-url"]}, "family"),
        ({"weight": {"value": "250.000000"}}, "weight"),
        ({"id": 0}, "id"),
        ({"regular_prize": 69.59}, "regular_prize"),  # a misspelled field must not pass unnoticed
    ],
)
def test_invalid_product_is_rejected(changes, field):
    with pytest.raises(ValidationError) as exc_info:
        Product.model_validate(product_data(**changes))
    assert exc_info.value.errors()[0]["loc"][0] == field


@pytest.mark.parametrize(
    ("price", "regular_price"),
    [
        ("80", "10"),  # a parser that swapped the two fields
        ("10.01", "10"),
    ],
)
def test_price_above_regular_price_is_rejected(price, regular_price):
    with pytest.raises(ValidationError, match="price can't exceed regular_price"):
        Product.model_validate(product_data(price=price, regular_price=regular_price))


@pytest.mark.parametrize(
    "field",
    ["id", "url", "name", "description", "price", "regular_price", "has_discount", "category_ids", "images"],
)
def test_product_without_a_required_field_is_rejected(field):
    with pytest.raises(ValidationError):
        Product.model_validate(without(product_data(), field))


@pytest.mark.parametrize(
    "data",
    [
        category_data(name=" "),
        category_data(url="/104-olejki"),
        category_data(id=0),
        category_data(parent_id=0),
        without(category_data(), "parent_id"),  # forgetting the parent must not create a top-level category
    ],
)
def test_invalid_category_is_rejected(data):
    with pytest.raises(ValidationError):
        Category.model_validate(data)


""" ========== LOGGING INVALID RECORDS =========="""


def test_valid_record_is_returned_and_nothing_is_logged(caplog):
    with caplog.at_level(logging.WARNING):
        product = validate_record(Product, product_data(), PRODUCT_URL)
    assert isinstance(product, Product)
    assert caplog.text == ""


def test_invalid_record_goes_to_scraper_log_with_its_url(log_file):
    assert validate_record(Product, product_data(description=""), PRODUCT_URL) is None
    logged = log_file.read_text(encoding="utf-8")
    assert "ERROR" in logged
    assert f"Invalid Product at {PRODUCT_URL}" in logged
    assert "description" in logged


def test_log_entry_is_one_line_and_lists_every_problem_without_page_content(caplog):
    empty_html = "<p>&nbsp;</p>\n" * 50
    with caplog.at_level(logging.ERROR):
        validate_record(Product, product_data(description=empty_html, price=0, images=[{}]), PRODUCT_URL)
    message = caplog.messages[0]
    assert "\n" not in message
    assert "description:" in message
    assert "price:" in message
    assert "images.0.source_url:" in message  # points to the exact nested field
    assert "&nbsp;" not in message


def test_invalid_record_does_not_stop_the_run_and_is_not_saved(caplog):
    records = [product_data(id=1), product_data(id=2, description=""), product_data(id=3)]
    with caplog.at_level(logging.ERROR):
        validated = [validate_record(Product, record, PRODUCT_URL) for record in records]
    assert [product.id for product in validated if product] == [1, 3]
    assert len(caplog.records) == 1


def test_price_above_regular_price_is_logged_with_its_url(caplog):
    with caplog.at_level(logging.ERROR):
        assert validate_record(Product, product_data(price="80", regular_price="10"), PRODUCT_URL) is None
    assert f"Invalid Product at {PRODUCT_URL}" in caplog.text
    assert "price can't exceed regular_price" in caplog.text


""" ========== JSON SCHEMA =========="""


def test_schema_describes_both_record_types():
    definitions = json_schema()["$defs"]
    assert {"id", "name", "url", "parent_id"} == set(definitions["Category"]["properties"])
    assert {"name", "description", "price", "images"} <= set(definitions["Product"]["properties"])
    assert {"name", "description", "price", "images"} <= set(definitions["Product"]["required"])


def test_schema_describes_a_saved_product():
    """Prices are saved as strings, so the schema must say the same."""
    product = json.loads(Product.model_validate(product_data(price=17.2)).model_dump_json())
    price_schema = json_schema()["$defs"]["Product"]["properties"]["price"]
    assert product["price"] == "17.2"
    assert price_schema["type"] == "string"
    assert re.search(price_schema["pattern"], product["price"])
    assert not re.search(price_schema["pattern"], "69.58764")


@pytest.mark.parametrize(
    ("value", "saved"),
    [
        ("69.590000", "69.59"),
        ("64.720", "64.72"),
        ("0.10", "0.1"),
        ("100.00", "100"),
        ("1e2", "100"),
        ("1.5e1", "15"),
        ("1e-2", "0.01"),
        (17.2, "17.2"),
        ("9999999999.99", "9999999999.99"),  # the largest accepted price
    ],
)
def test_saved_price_matches_the_schema_and_reads_back_the_same(value, saved):
    """A price may arrive in many spellings, but only the form the schema allows may reach the results file."""
    line = Product.model_validate(product_data(price=value, regular_price=value)).model_dump_json()
    properties = json_schema()["$defs"]["Product"]["properties"]
    for field in ("price", "regular_price"):
        assert json.loads(line)[field] == saved
        assert re.search(properties[field]["pattern"], saved)
    assert Product.model_validate_json(line).model_dump_json() == line


def test_committed_schema_is_up_to_date():
    saved = json.loads(config.SCHEMA_FILE.read_text(encoding="utf-8"))
    assert saved == json_schema(), "models changed: run `python -m scraper schema`"


def test_schema_command_writes_the_file_without_network(tmp_path, monkeypatch):
    target = tmp_path / "scraper-results" / "schema.json"
    monkeypatch.setattr(config, "SCHEMA_FILE", target)
    monkeypatch.setattr("scraper.__main__.setup_logging", lambda *args: None)
    monkeypatch.setattr("scraper.__main__.HttpClient", lambda **kwargs: pytest.fail("the client was created"))
    assert main(["schema"]) == 0
    assert json.loads(target.read_text(encoding="utf-8")) == json_schema()
