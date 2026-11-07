"""Thread-safe in-memory store of deliberation results.

The store keeps the most recent ``capacity`` results (FIFO eviction) and is
process-local by design: MODEL-COUNCIL deliberately ships without a
database so the default deployment has zero data-retention surface.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from model_council.engine.results import DeliberationResult


class DeliberationStore:
    def __init__(self, capacity: int = 128):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._items: OrderedDict[str, DeliberationResult] = OrderedDict()
        self._lock = threading.Lock()

    def save(self, result: DeliberationResult) -> None:
        with self._lock:
            self._items[result.council_id] = result
            self._items.move_to_end(result.council_id)
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)

    def get(self, council_id: str) -> DeliberationResult | None:
        with self._lock:
            return self._items.get(council_id)

    def list(self) -> list[DeliberationResult]:
        with self._lock:
            return list(self._items.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
