"""L2 в PostgreSQL. Замок живёт только внутри короткой транзакции."""

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol

from starflow.cache.ttl import CachedValue
from starflow.domain.time import now_utc
from starflow.repositories.sql import ForecastCacheRepository


class CacheWork(Protocol):
    forecast_cache: ForecastCacheRepository

    async def commit(self) -> None: ...

    async def __aenter__(self) -> "CacheWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class PostgresLevelTwo:
    def __init__(self, uow_factory: Callable[[], CacheWork]) -> None:
        self._uow_factory = uow_factory

    async def read(self, key: str, now: datetime) -> CachedValue | None:
        async with self._uow_factory() as uow:
            await uow.forecast_cache.lock(key)
            found = await uow.forecast_cache.read_fresh(key, now)
            await uow.commit()
        if found is None:
            return None
        payload, expires_at = found
        return CachedValue(payload, expires_at)

    async def note_hit(self, key: str, now: datetime) -> CachedValue | None:
        return await self.read(key, now)

    async def write(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> CachedValue:
        async with self._uow_factory() as uow:
            await uow.forecast_cache.lock(key)
            found = await uow.forecast_cache.read_fresh(key, now_utc())
            if found is None:
                stored_payload, stored_until = await uow.forecast_cache.write_shared(
                    key,
                    kind,
                    payload,
                    expires_at,
                )
            else:
                stored_payload, stored_until = found
            await uow.commit()
        return CachedValue(stored_payload, stored_until)

    async def overwrite(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> CachedValue:
        async with self._uow_factory() as uow:
            await uow.forecast_cache.lock(key)
            stored_payload, stored_until = await uow.forecast_cache.overwrite(
                key,
                kind,
                payload,
                expires_at,
            )
            await uow.commit()
        return CachedValue(stored_payload, stored_until)
