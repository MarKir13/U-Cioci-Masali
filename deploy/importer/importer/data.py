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


def load_products(data_dir: Path, schema: dict) -> tuple[list[dict], list[tuple[int, str]]]:
    """Valid products, and (id, reason) for the rest. A product whose image file is missing is invalid."""
    validator = validator_for(schema, "Product")
    records = []
    with (data_dir / "products.jsonl").open(encoding="utf-8") as lines:
        for line in lines:
            if line.strip():
                records.append(json.loads(line))
    valid, rejected = _split(records, validator)

    ok = []
    for product in valid:
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
