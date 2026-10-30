import asyncio
import time
from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.errors import PremiumRequired
from starflow.domain.records import PlaceHit
from starflow.domain.time import now_utc
from starflow.repositories.sql import GeocodeCacheRepository, SubscriptionRepository
from starflow.services.profile import normalize_place_query


class PlaceLookup(Protocol):
    async def search(self, query: str) -> list[PlaceHit]: ...


class PlaceStore(Protocol):
    geocodes: GeocodeCacheRepository
    subscriptions: SubscriptionRepository

    async def commit(self) -> None: ...


class PlaceWork(Protocol):
    async def __aenter__(self) -> PlaceStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class RequestPace:
    """Один запрос к геокодеру в секунду на весь процесс."""

    def __init__(self, interval_sec: float = 1) -> None:
        self._interval = interval_sec
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            if delay > 0:
                await asyncio.sleep(delay)
                now = time.monotonic()
            self._next = now + self._interval


class PlaceService:
    def __init__(
        self,
        uow_factory: Callable[[], PlaceWork],
        lookup: PlaceLookup,
        pace: RequestPace,
        user_gap_sec: float = 0.4,
    ) -> None:
        self._uow_factory = uow_factory
        self._lookup = lookup
        self._pace = pace
        self._user_gap = user_gap_sec
        self._guard = asyncio.Lock()
        self._user_locks: dict[UUID, asyncio.Lock] = {}
        self._user_next: dict[UUID, float] = {}

    async def search(self, user_id: UUID, query: str) -> list[PlaceHit]:
        normalized = normalize_place_query(query)
        if len(normalized) < 2:
            return []
        cached = await self._cached(user_id, normalized)
        if cached is not None:
            return cached
        user_lock = await self._lock_for(user_id)
        async with user_lock:
            cached = await self._cached(user_id, normalized)
            if cached is not None:
                return cached
            await self._gap(user_id)
            await self._pace.wait()
            hits = await self._lookup.search(normalized)
            async with self._uow_factory() as uow:
                if hits:
                    await uow.geocodes.store_results(normalized, hits)
                    await uow.commit()
            return hits

    async def _cached(self, user_id: UUID, normalized: str) -> list[PlaceHit] | None:
        async with self._uow_factory() as uow:
            return await uow.geocodes.get_results(normalized)

    async def _lock_for(self, user_id: UUID) -> asyncio.Lock:
        async with self._guard:
            lock = self._user_locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._user_locks[user_id] = lock
            return lock

    async def _gap(self, user_id: UUID) -> None:
        async with self._guard:
            now = time.monotonic()
            delay = self._user_next.get(user_id, 0.0) - now
            self._user_next[user_id] = max(now, self._user_next.get(user_id, 0.0)) + self._user_gap
        if delay > 0:
            await asyncio.sleep(delay)
