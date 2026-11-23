"""Reads the scraped results and validates every record against scraper-results/schema.json."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match


def load_schema(data_dir: Path) -> dict:
    return json.loads((data_dir / "schema.json").read_text(encoding="utf-8"))


def validator_for(schema: dict, name: str) -> Draft202012Validator:
    """A validator for one record type of the schema, such as "Product" or "Category"."""
    return Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": schema["$defs"]})


def problem(validator: Draft202012Validator, record: dict) -> str | None:
    """The main reason a record breaks the schema, or None if it is valid."""
    error = best_match(validator.iter_errors(record))
    if error is None:
        return None
    where = ".".join(str(part) for part in error.absolute_path) or "record"
    return f"{where}: {error.message}"


def load_categories(data_dir: Path, schema: dict) -> tuple[list[dict], list[tuple[int, str]]]:
    """Valid categories, and (id, reason) for the rest."""
    validator = validator_for(schema, "Category")
    records = json.loads((data_dir / "categories.json").read_text(encoding="utf-8"))
    return _split(records, validator)


def load_products(data_dir: Path, schema: dict) -> tuple[list[dict], list[tuple[int, str]], list[tuple[int, str]]]:
    """Valid products, (id, reason) for the invalid ones, and (line number, reason) for unreadable lines.

    A line that is not a JSON object is unreadable: it has no product ID, so the caller cannot tell which
    product it was. Image files are not checked here but by with_images(), only for the products a run imports.
    """
    validator = validator_for(schema, "Product")
    records = []
    unreadable = []
    with (data_dir / "products.jsonl").open(encoding="utf-8") as lines:
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                unreadable.append((number, f"not valid JSON: {error.msg}"))
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                unreadable.append((number, "not a JSON object"))
    valid, rejected = _split(records, validator)
    return valid, rejected, unreadable


def load_brands(data_dir: Path, schema: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    """Valid brand records of brands.json, and (name, reason) for the rest.

    The file is optional: a results folder from before the brand pages has none, and the manufacturers then get
    only their names. A schema without `Brand` (the same old folder) is treated the same way.
    """
    path = data_dir / "brands.json"
    if not path.is_file() or "Brand" not in schema["$defs"]:
        return [], []
    validator = validator_for(schema, "Brand")
    valid, rejected = [], []
    for record in json.loads(path.read_text(encoding="utf-8")):
        reason = problem(validator, record)
        if reason is None:
            valid.append(record)
        else:
            rejected.append((str(record.get("name", "?")), reason))
    return valid, rejected


def with_images(products: list[dict], data_dir: Path) -> tuple[list[dict], list[tuple[int, str]]]:
    """The products whose image files are all there, and (id, reason) for the rest.

    Called on the selected products only, so a subset run (--limit, --categories) needs only the images of its
    own products, as with the small subset archive of the init command.
    """
    ok, rejected = [], []
    for product in products:
        missing = [i["local_path"] for i in product["images"] if not (data_dir / i["local_path"]).is_file()]
        if missing:
            rejected.append((product["id"], f"image file missing: {', '.join(missing)}"))
        else:
            ok.append(product)
    return ok, rejected


def _split(records: list[dict], validator: Draft202012Validator) -> tuple[list[dict], list[tuple[int, str]]]:
    valid, rejected = [], []
    for record in records:
        reason = problem(validator, record)
        if reason is None:
            valid.append(record)
        else:
            rejected.append((record.get("id", 0), reason))
    return valid, rejected
