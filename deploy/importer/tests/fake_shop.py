"""An in-memory stand-in for ShopApi, for testing whole import steps without a shop.

It stores what the importer writes and returns it the way the real API reads it back: every value as text,
multilingual fields as plain text (one language), associations as lists of {"id": "..."}. It also copies the
few things PrestaShop does on its own that the importer relies on:
- a new category goes last among its siblings, whatever position it is sent (Category::add), but the answer
  to the POST still shows the position sent (the webservice renders the object it kept in memory); an update
  stores the position as sent;
- a new product or combination gets a stock row with quantity 0;
- a product's own stock row is the sum of its combinations' rows (StockAvailable::postSave);
- a combination with default_on becomes the product's default combination (Product::updateDefaultAttribute),
  and an update of the product that leaves out id_default_combination empties it;
- deleting a combination deletes its stock row and its specific prices.

It is not PrestaShop: it does not check required fields or values. What it shows is that the importer's
own logic finds what it wrote before and writes nothing twice.
"""

import itertools

from importer.api import Lang
from importer.report import Timings

LANGUAGE_FIELDS = {"name", "public_name", "description", "description_short", "link_rewrite"}


class FakeApi:
    def __init__(self) -> None:
        self.dry_run = False
        self.lang_ids = [1]
        # Like ShopApi.timings: the steps record their waits here (steps.import_product)
        self.timings = Timings()
        self.records: dict[str, dict[int, dict]] = {}
        self._ids = itertools.count(100)
        self.writes: list[tuple[str, str]] = []  # (method, resource) of every write, for the tests
        # Home (root) category and one VAT group of 23%
        self.add("categories", {"id_parent": "1", "name": "Strona główna", "is_root_category": "1", "level_depth": "1"})
        self.add("taxes", {"rate": "23.000"})
        self.add("tax_rule_groups", {"active": "1", "deleted": "0"})
        tax_id = self.ids("taxes")[0]
        group_id = self.ids("tax_rule_groups")[0]
        self.add("tax_rules", {"id_tax_rules_group": str(group_id), "id_tax": str(tax_id)})

    # --- helpers for the tests ---

    def add(self, resource: str, record: dict) -> int:
        record_id = next(self._ids)
        self.records.setdefault(resource, {})[record_id] = {"id": str(record_id), **record}
        return record_id

    def ids(self, resource: str) -> list[int]:
        return sorted(self.records.get(resource, {}))

    def all(self, resource: str) -> list[dict]:
        return [self.records[resource][i] for i in self.ids(resource)]

    @property
    def home_id(self) -> int:
        return self.ids("categories")[0]

    @property
    def tax_group_id(self) -> int:
        return self.ids("tax_rule_groups")[0]

    # --- the ShopApi interface ---

    def list(self, resource: str, display: str = "full", filters: dict | None = None) -> list[dict]:
        records = self.all(resource)
        for field, value in (filters or {}).items():
            records = [r for r in records if str(r.get(field, "")) == str(value)]
        if display == "full":
            return [dict(r) for r in records]
        # Like the real API: only the fields asked for, as in display=[id,name]
        wanted = {name.strip() for name in display.strip("[]").split(",")}
        return [{name: value for name, value in r.items() if name in wanted} for r in records]

    def get(self, resource: str, record_id: int) -> dict:
        return dict(self.records[resource][record_id])

    def create(self, resource: str, fields: dict) -> dict:
        self.writes.append(("POST", resource))
        record_id = self.add(resource, self._read_back(fields))
        record = self.records[resource][record_id]
        if resource == "products":
            record.setdefault("associations", {})
            record["id_default_combination"] = "0"
            stock_id = self._new_stock_row(record_id, 0)
            record["associations"]["stock_availables"] = [{"id": str(stock_id), "id_product_attribute": "0"}]
        elif resource == "combinations":
            self._new_stock_row(int(fields["id_product"]), record_id)
            self._after_combination(record)
        elif resource == "categories":
            sent = record.get("position")
            siblings = [
                int(other.get("position") or 0)
                for other in self.all("categories")
                if other["id_parent"] == record["id_parent"] and other["id"] != record["id"]
            ]
            record["position"] = str(max(siblings) + 1 if siblings else 0)
            # PrestaShop answers with the object it kept in memory, which still has the position sent
            return {**record, "position": sent} if sent is not None else dict(record)
        return dict(record)

    def update(self, resource: str, record_id: int, fields: dict) -> None:
        self.writes.append(("PUT", resource))
        old = self.records[resource][record_id]
        record = {"id": str(record_id), **self._read_back(fields)}
        if resource == "products":
            # Associations not sent are kept (images, stock), as in the real API
            record["associations"] = {**old.get("associations", {}), **record.get("associations", {})}
            record.setdefault("id_default_combination", "0")
        self.records[resource][record_id] = record
        if resource == "combinations":
            self._after_combination(record)
        if resource == "stock_availables" and int(record["id_product_attribute"]):
            self._sum_stock(int(record["id_product"]))

    def delete(self, resource: str, record_id: int) -> None:
        self.writes.append(("DELETE", resource))
        record = self.records[resource].pop(record_id)
        if resource == "combinations":
            product_id = int(record["id_product"])
            for kind in ("stock_availables", "specific_prices"):
                for other in self.all(kind):
                    if other["id_product_attribute"] == str(record_id):
                        del self.records[kind][int(other["id"])]
            self._sum_stock(product_id)

    def upload_image(self, product_id: int, path) -> None:
        self.writes.append(("POST", "images"))
        image_id = next(self._ids)
        images = self.records["products"][product_id].setdefault("associations", {}).setdefault("images", [])
        images.append({"id": str(image_id)})

    def delete_image(self, product_id: int, image_id: int) -> None:
        self.writes.append(("DELETE", "images"))
        images = self.records["products"][product_id]["associations"]["images"]
        images[:] = [i for i in images if i["id"] != str(image_id)]

    # --- what PrestaShop does on its own ---

    @staticmethod
    def _read_back(fields: dict) -> dict:
        record = {}
        for name, value in fields.items():
            if name == "associations":
                record[name] = {group: [{"id": str(item["id"])} for _, item in items] for group, items in value.items()}
            elif isinstance(value, Lang) or name in LANGUAGE_FIELDS:
                record[name] = str(value)
            else:
                record[name] = "" if value is None else str(value)
        return record

    def _new_stock_row(self, product_id: int, combination_id: int) -> int:
        row = {
            "id_product": str(product_id),
            "id_product_attribute": str(combination_id),
            "id_shop": "1",
            "id_shop_group": "0",
            "quantity": "0",
            "out_of_stock": "2",
        }
        return self.add("stock_availables", row)

    def _after_combination(self, combination: dict) -> None:
        if combination.get("default_on") == "1":
            product = self.records["products"][int(combination["id_product"])]
            product["id_default_combination"] = combination["id"]

    def _sum_stock(self, product_id: int) -> None:
        rows = [r for r in self.all("stock_availables") if r["id_product"] == str(product_id)]
        total = sum(int(r["quantity"]) for r in rows if r["id_product_attribute"] != "0")
        for row in rows:
            if row["id_product_attribute"] == "0":
                row["quantity"] = str(total)
