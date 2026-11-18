"""Counts of what the import did, per resource, and the problems it met.

Steps run in several threads at once, so every change to the counts goes through a lock.
"""

import logging
import threading
from collections import Counter

log = logging.getLogger("importer")

# Order of the rows in the summary
RESOURCES = [
    "categories",
    "manufacturers",
    "products",
    "stock",
    "specific_prices",
    "images",
    "product_options",
    "product_option_values",
    "combinations",
]
COLUMNS = ["created", "updated", "unchanged", "deleted", "rejected"]


class Report:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counts: dict[str, Counter] = {resource: Counter() for resource in RESOURCES}

    def count(self, resource: str, outcome: str, number: int = 1) -> None:
        """outcome: created, updated, unchanged or deleted."""
        with self._lock:
            self.counts[resource][outcome] += number

    def reject(self, resource: str, key: object, reason: str) -> None:
        """A record that was not saved: invalid data or an error from the shop. Goes to the log."""
        with self._lock:
            self.counts[resource]["rejected"] += 1
        log.error("REJECTED %s %s: %s", resource, key, reason)

    @property
    def rejected(self) -> int:
        return sum(counts["rejected"] for counts in self.counts.values())

    def rejected_of(self, resource: str) -> int:
        with self._lock:
            return self.counts[resource]["rejected"]

    def summary(self) -> str:
        width = max(len(r) for r in RESOURCES)
        lines = [" " * width + "".join(f"{c:>11}" for c in COLUMNS)]
        for resource in RESOURCES:
            counts = self.counts[resource]
            lines.append(f"{resource:<{width}}" + "".join(f"{counts[c]:>11}" for c in COLUMNS))
        return "\n".join(lines)
