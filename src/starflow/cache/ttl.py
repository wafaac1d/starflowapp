"""L1: ограниченный LRU. Срок записи не длиннее срока строки L2."""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CachedValue:
    payload: dict[str, object]
    expires_at: datetime


class TtlCache:
    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise ValueError("memory cache size must be positive")
        self._max_size = max_size
        self._items: OrderedDict[str, CachedValue] = OrderedDict()

    def get(self, key: str, now: datetime) -> CachedValue | None:
        found = self._items.get(key)
        if found is None:
            return None
        if found.expires_at <= now:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return found

    def drop(self, key: str) -> None:
        self._items.pop(key, None)

    def put(self, key: str, value: CachedValue) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self._max_size:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)
