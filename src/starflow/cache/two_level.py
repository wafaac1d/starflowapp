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

    async def get_or_create(
        self,
        key: str,
        kind: str,
        expires_at: datetime,
        producer: Callable[[], Awaitable[dict[str, object]]],
    ) -> CacheHit:
        now = self._clock()
        cached = self._memory.get(key, now)
        if cached is not None:
            still = await self._store.note_hit(key, now)
            if still is not None:
                return CacheHit(still.payload, still.expires_at, False)
            self._memory.drop(key)
        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                now = self._clock()
                fresh = await self._store.read(key, now)
                if fresh is not None:
                    self._memory.put(key, fresh)
                    return CacheHit(fresh.payload, fresh.expires_at, False)
                produced = await producer()
                now = self._clock()
                again = await self._store.read(key, now)
                if again is not None:
                    self._memory.put(key, again)
                    return CacheHit(again.payload, again.expires_at, False)
                stored = await self._store.write(key, kind, produced, expires_at)
                remembered = CachedValue(stored.payload, stored.expires_at)
                self._memory.put(key, remembered)
                return CacheHit(remembered.payload, remembered.expires_at, True)
        except asyncio.CancelledError:
            raise

    async def remember(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> None:
        stored = await self._store.overwrite(key, kind, payload, expires_at)
        self._memory.put(key, stored)
