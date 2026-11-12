"""Schema of the scraped data. Every record is validated here before it is saved."""

import html
import json
import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveInt,
    StringConstraints,
    ValidationError,
    WithJsonSchema,
    field_validator,
    model_validator,
)
from pydantic.json_schema import models_json_schema

log = logging.getLogger(__name__)


def has_visible_text(value: str) -> bool:
    """Descriptions are HTML, so `<p>&nbsp;</p>` counts as empty too."""
    # delete HTML tags [^>] means whatever other than '>' and * means however long => '<tag>text</tag>' becomes 'text'
    return bool(html.unescape(re.sub(r"<[^>]*>", "", value)).strip())


def _require_visible_text(value: str) -> str:
    if not has_visible_text(value):
        raise ValueError("no visible text")
    return value


def _blank_to_none(value: object) -> object:
    """A blank optional field means the shop has no value, which is no reason to drop the whole product."""
    return None if isinstance(value, str) and not value.strip() else value


def _normalize_price(value: Decimal) -> Decimal:
    """Normalizes the price, removing redundant zeros and converts scientific notation"""
    return Decimal(format(value.normalize(), "f"))


"""Create reusable data types using Annotated"""
# Non-empty stripped string
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Stripped string (may be empty)
OptionalText = Annotated[Text | None, BeforeValidator(_blank_to_none)]

# non empty HTML tag (saved with the Tag)
Description = Annotated[Text, AfterValidator(_require_visible_text)]

# Two decimal places, so a raw value like 69.58764 fails unless the parser has rounded it.
# Decimals are saved as JSON strings, which is what the schema has to describe.
# max_digits rejects values like 1e30 before normalize(), which rounds past 28 digits and can raise Overflow.
Price = Annotated[
    Decimal,
    Field(gt=0, max_digits=12, decimal_places=2),
    AfterValidator(_normalize_price),
    # Saved as string with an optional .xx
    WithJsonSchema({"type": "string", "pattern": r"^\d+(\.\d{1,2})?$"}, mode="serialization"),
    # ^       => start of text
    # \d+     => one or more number
    # (...)?  => optional group (doesn't have to occur because of '?')
    # \.      => dot character
    # \d{1,2} => 1 or 2 digits ("{a,b}" specifies range inclusive both sides)
    # $       => end of text (not '$' character)
]


class Record(BaseModel):
    # A misspelled optional field would otherwise be dropped without a word and leave the real one empty.
    model_config = ConfigDict(extra="forbid")


class Category(Record):
    """A category or subcategory. `parent_id` is null for top-level categories."""

    id: PositiveInt
    name: Text
    url: HttpUrl
    # No default: a parser that forgets the parent must fail, not create a top-level category.
    parent_id: PositiveInt | None


class Image(Record):
    """A product image. `local_path` is filled in once the file has been downloaded."""

    source_url: HttpUrl
    local_path: str | None = None


class RawWeight(Record):
    """Weight exactly as on the page. The unit is unreliable, so it is converted only on import."""

    value: Text
    unit: Text


class Product(Record):
    """A product. Variants are separate products, linked through `family`."""

    id: PositiveInt
    url: HttpUrl
    name: Text
    description: Description
    price: Price
    regular_price: Price
    has_discount: bool
    # field that is 0 <= x <= 100
    vat_rate: Annotated[float, Field(ge=0, le=100)] | None = None
    brand: OptionalText = None
    ean: OptionalText = None
    size: OptionalText = None
    color: OptionalText = None
    material: OptionalText = None
    pattern: OptionalText = None
    weight: RawWeight | None = None
    family: list[HttpUrl] = Field(default_factory=list)
    # must have at least 1 category(may have more -> min_length=1)
    category_ids: list[PositiveInt] = Field(min_length=1)
    # same with images
    images: list[Image] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_prices(self) -> Self:
        """Current price can't exceed the regular price"""
        if self.price <= self.regular_price:
            return self
        raise ValueError("price can't exceed regular_price")

    @field_validator("category_ids", "family")
    @classmethod
    def _no_duplicates(cls, values: list) -> list:
        """Can't have duplicates in fields listed above"""
        if len(values) != len(set(values)):
            raise ValueError("contains duplicates")
        return values

    @field_validator("images")
    @classmethod
    def _no_duplicate_images(cls, images: list[Image]) -> list[Image]:
        """images can't be converted into set so check only source urls"""
        urls = [str(image.source_url) for image in images]
        if len(urls) != len(set(urls)):
            raise ValueError("contains duplicate source_url")
        return images


def validate_record[T: Record](model: type[T], data: dict, url: str, problems: list[str] | None = None) -> T | None:
    """Return the validated record, or log why it is invalid and return None so that the run can go on.

    If `problems` is given, the reason is also appended to it (the crawl saves it in rejected.json).
    """
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        reason = "; ".join(f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors())
        log.error("Invalid %s at %s: %s", model.__name__, url, reason)
        if problems is not None:
            problems.append(reason)
        return None


def json_schema() -> dict:
    """JSON schema of the saved records: `#/$defs/Category` and `#/$defs/Product`."""
    _, schema = models_json_schema([(Category, "serialization"), (Product, "serialization")], title="Scraper results")
    return schema


def export_schema(path: Path) -> None:
    # create path if doesn't exist (just folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    # write the file now
    path.write_text(json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("Saved the JSON schema to %s", path)
