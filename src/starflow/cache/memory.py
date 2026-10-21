from collections import OrderedDict
from collections.abc import Iterator


class MemoryCache:
    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise ValueError("memory cache size must be positive")
        self._max_size = max_size
        self._items: OrderedDict[str, object] = OrderedDict()

    def get(self, key: str) -> object | None:
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def set(self, key: str, value: object) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self._max_size:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)
