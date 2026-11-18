"""Products with variants (D3, issue #73): reads and checks deploy/importer/variants.json.

The source shop has no PrestaShop combinations. Its variants are separate products linked by its `ndx-family`
module (`family` in products.jsonl). variants.json picks a few such families and says which source product is
which value of one attribute, such as "Pojemność: 50 ml". The importer then makes one product with a combination
per value, instead of the separate products (ADR 0009).

No network and no shop here: everything can be unit-tested (tests/test_variants.py).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from . import data, mapping

# Where the file is: next to the `importer` package, so the image build copies it (Dockerfile)
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "variants.json"

# One entry of "products" in variants.json. Each entry is checked on its own, so one broken entry does not stop
# the others.
DEFINITION_SCHEMA = {
    "type": "object",
    "required": ["name", "attribute_group", "values"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 128},
        "attribute_group": {"type": "string", "minLength": 1, "maxLength": 64},
        "values": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["value", "source_id"],
                "additionalProperties": False,
                "properties": {
                    "value": {"type": "string", "minLength": 1, "maxLength": 128},
                    "source_id": {"type": "integer"},
                },
            },
        },
    },
}
DEFINITION = Draft202012Validator(DEFINITION_SCHEMA)


@dataclass(frozen=True)
class Variant:
    value: str  # the attribute value, such as "50 ml"
    product: dict  # the source product it comes from, as in products.jsonl


@dataclass(frozen=True)
class VariantProduct:
    """One product with combinations. The first variant is the default one."""

    name: str
    group: str  # the attribute group, such as "Pojemność"
    variants: list[Variant]

    @property
    def default(self) -> dict:
        return self.variants[0].product

    @property
    def source_ids(self) -> set[int]:
        return {v.product["id"] for v in self.variants}


def load(path: Path) -> list:
    """The entries of variants.json, not checked yet. A missing file means no products with variants."""
    if not path.is_file():
        return []
    content = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict) or not isinstance(content.get("products"), list):
        raise ValueError(f'{path}: expected an object with a list "products"')
    return content["products"]


def resolve(definitions: list, products: list[dict]) -> tuple[list[VariantProduct], list[tuple[str, str]]]:
    """The valid entries with their source products, and (name, reason) for the rest.

    `products` are the valid source products. An entry is rejected when it breaks the schema, repeats a value
    or a source product, names a source product that is not among them (unknown, or rejected by the schema of
    products.jsonl), or one already used by an earlier entry, or joins products with different VAT rates
    (a combination has no VAT of its own). The source products of a rejected entry are imported on their own,
    as without variants.json.
    """
    by_id = {p["id"]: p for p in products}
    used: set[int] = set()
    valid, rejected = [], []
    for number, definition in enumerate(definitions, 1):
        name = definition.get("name") if isinstance(definition, dict) else None
        key = name if isinstance(name, str) and name else f"entry {number}"
        reason = _problem(definition, by_id, used)
        if reason:
            rejected.append((key, reason))
            continue
        variants = [Variant(v["value"], by_id[v["source_id"]]) for v in definition["values"]]
        product = VariantProduct(definition["name"], definition["attribute_group"], variants)
        used |= product.source_ids
        valid.append(product)
    return valid, rejected


def with_images(products: list[VariantProduct], data_dir: Path) -> tuple[list[VariantProduct], list[tuple[str, str]]]:
    """The products whose source products all have their image files, and (name, reason) for the others.

    A product with variants uploads the images of all its source products, so one missing file rejects it whole.
    It still counts as in the data, so the delete step keeps its copy from an earlier run.
    """
    complete, rejected = [], []
    for product in products:
        _, missing = data.with_images([v.product for v in product.variants], data_dir)
        if missing:
            rejected.append((product.name, "; ".join(f"source product {i}: {reason}" for i, reason in missing)))
        else:
            complete.append(product)
    return complete, rejected


def _problem(definition: object, by_id: dict[int, dict], used: set[int]) -> str | None:
    reason = data.problem(DEFINITION, definition)
    if reason:
        return reason
    values = [v["value"] for v in definition["values"]]
    source_ids = [v["source_id"] for v in definition["values"]]
    if len(set(values)) < len(values):
        return "a value is listed twice"
    if len(set(source_ids)) < len(source_ids):
        return "a source product is listed twice"
    missing = [i for i in source_ids if i not in by_id]
    if missing:
        return f"source product(s) not in the data or rejected: {', '.join(map(str, missing))}"
    taken = [i for i in source_ids if i in used]
    if taken:
        return f"source product(s) already used by an earlier entry: {', '.join(map(str, taken))}"
    if len({by_id[i]["vat_rate"] for i in source_ids}) > 1:
        return "the source products have different VAT rates"
    return None


def product_record(product: VariantProduct) -> dict:
    """The product with combinations, written like a record of products.jsonl, so that steps.product_fields()
    can make it like any other product.

    It is the default variant's source product with: the name from variants.json (and a URL slug made from it),
    the categories of all variants, the images of all variants (the default variant's first, so its first image
    is the cover), no barcode (each combination has its own) and no promotion (each combination has its own).
    Its price and weight are the default variant's; the combinations store the differences.
    """
    default = product.default
    categories: list[int] = []
    for variant in product.variants:
        categories += [c for c in variant.product["category_ids"] if c not in categories]
    return {
        **default,
        "name": product.name,
        "link_rewrite": mapping.slug(product.name),
        "category_ids": categories,
        "images": [image for v in product.variants for image in v.product["images"]],
        "ean": None,
        "price": default["regular_price"],
        "has_discount": False,
    }


def values_by_group(products: list[VariantProduct]) -> dict[str, list[str]]:
    """Attribute group -> its values, in the order the shop should list them (smallest number first)."""
    groups: dict[str, set[str]] = {}
    for product in products:
        groups.setdefault(product.group, set()).update(v.value for v in product.variants)
    return {group: sorted(values, key=mapping.value_order) for group, values in sorted(groups.items())}
