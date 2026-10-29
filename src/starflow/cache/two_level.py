"""Два уровня кэша. Вызов модели происходит вне транзакции PostgreSQL."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from starflow.cache.ttl import CachedValue, TtlCache
from starflow.domain.time import now_utc


@dataclass(frozen=True)
class CacheHit:
    payload: dict[str, object]
    expires_at: datetime
    generated: bool


def _reusable(payload: dict[str, object]) -> bool:
    return payload.get("source") != "fallback"


class LevelTwo(Protocol):
    async def read(self, key: str, now: datetime) -> CachedValue | None: ...

    async def note_hit(self, key: str, now: datetime) -> CachedValue | None: ...

    async def write(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> CachedValue: ...

    async def overwrite(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> CachedValue: ...


class TwoLevelCache:
    def __init__(
        self,
        memory: TtlCache,
        store: LevelTwo,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._memory = memory
        self._store = store
        self._clock = clock or now_utc
        self._locks: dict[str, asyncio.Lock] = {}
        self.l1_hits = 0
        self.l1_misses = 0
        self.l2_hits = 0
        self.generations = 0

    async def get_or_create(
        self,
        key: str,
        kind: str,
        expires_at: datetime,
        producer: Callable[[], Awaitable[dict[str, object]]],
    ) -> CacheHit:
        now = self._clock()
        cached = self._memory.get(key, now)
        if cached is not None and _reusable(cached.payload):
            self.l1_hits += 1
            still = await self._store.note_hit(key, now)
            if still is not None and _reusable(still.payload):
                return CacheHit(still.payload, still.expires_at, False)
            self._memory.drop(key)
        elif cached is not None:
            self._memory.drop(key)
        self.l1_misses += 1
        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                now = self._clock()
                fresh = await self._store.read(key, now)
                if fresh is not None and _reusable(fresh.payload):
                    self.l2_hits += 1
                    self._memory.put(key, fresh)
                    return CacheHit(fresh.payload, fresh.expires_at, False)
                produced = await producer()
                if not _reusable(produced):
                    return CacheHit(produced, expires_at, False)
                now = self._clock()
                again = await self._store.read(key, now)
                if again is not None and _reusable(again.payload):
                    self.l2_hits += 1
                    self._memory.put(key, again)
                    return CacheHit(again.payload, again.expires_at, False)
                if fresh is not None or (again is not None and not _reusable(again.payload)):
                    stored = await self._store.overwrite(key, kind, produced, expires_at)
                else:
                    stored = await self._store.write(key, kind, produced, expires_at)
                    if not _reusable(stored.payload):
                        stored = await self._store.overwrite(key, kind, produced, expires_at)
                self.generations += 1
                remembered = CachedValue(stored.payload, stored.expires_at)
                self._memory.put(key, remembered)
                return CacheHit(remembered.payload, remembered.expires_at, True)
        finally:
            if not lock.locked():
                self._locks.pop(key, None)

    async def remember(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> None:
        stored = await self._store.overwrite(key, kind, payload, expires_at)
        self._memory.put(key, stored)
