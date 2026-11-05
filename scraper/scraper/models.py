"""Schema of the scraped data. Every record is validated here before it is saved."""

import html
import json
import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated

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
)
from pydantic.json_schema import models_json_schema

log = logging.getLogger(__name__)


def _require_visible_text(value: str) -> str:
    """Descriptions are HTML, so `<p>&nbsp;</p>` counts as empty too."""
    # delete HTML tags [^>] means whatever other than '>' and * means however long => '<tag>text</tag>' becomes 'text'
    if not html.unescape(re.sub(r"<[^>]*>", "", value)).strip():  # then check if empty
        raise ValueError("no visible text")
    return value


def _blank_to_none(value: object) -> object:
    """A blank optional field means the shop has no value, which is no reason to drop the whole product."""
    return None if isinstance(value, str) and not value.strip() else value


"""Create reusable data types using Annotated"""
# Non-empty stripped string
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Stripped string (may be empty)
OptionalText = Annotated[Text | None, BeforeValidator(_blank_to_none)]

# non empty HTML tag (saved with the Tag)
Description = Annotated[Text, AfterValidator(_require_visible_text)]

# Two decimal places, so a raw value like 69.58764 fails unless the parser has rounded it.
# Decimals are saved as JSON strings, which is what the schema has to describe.
Price = Annotated[
    Decimal,
    Field(gt=0, decimal_places=2),

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


def validate_record[T: Record](model: type[T], data: dict, url: str) -> T | None:
    """Return the validated record, or log why it is invalid and return None so that the run can go on."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
        )
        log.error("Invalid %s at %s: %s", model.__name__, url, problems)
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
