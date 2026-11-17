"""Counts of what the import did, per resource, and the problems it met.

Steps run in several threads at once, so every change to the counts goes through a lock.
"""

import logging
import threading
import time
from collections import Counter
from contextlib import contextmanager

log = logging.getLogger("importer")

# Order of the rows in the summary
RESOURCES = ["categories", "manufacturers", "products", "stock", "specific_prices", "images"]
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


class Timings:
    """Where the import spends its time, to find what to speed up (issue #71: the 15 minute limit).

    Phases are the steps of run(), measured on the wall clock. Work is anything done many times in several
    threads at once, such as one kind of API request: its seconds are summed over all threads, so with 8 workers
    the work can add up to more than the phase it belongs to. Comparing the two shows what the threads wait for.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.phases: dict[str, float] = {}
        self.work: dict[str, list] = {}  # name -> [count, seconds]

    def add(self, name: str, seconds: float) -> None:
        with self._lock:
            entry = self.work.setdefault(name, [0, 0.0])
            entry[0] += 1
            entry[1] += seconds

    @contextmanager
    def phase(self, name: str):
        started = time.monotonic()
        try:
            yield
        finally:
            self.phases[name] = time.monotonic() - started

    def summary(self) -> str:
        lines = ["phase (wall clock)                   seconds"]
        lines += [f"{name:<34}{seconds:>10.1f}" for name, seconds in self.phases.items()]
        lines.append("work (summed over threads)     count   seconds   average")
        by_time = sorted(self.work.items(), key=lambda item: -item[1][1])
        lines += [f"{name:<28}{count:>8}{seconds:>10.1f}{seconds / count:>10.3f}" for name, (count, seconds) in by_time]
        return "\n".join(lines)
