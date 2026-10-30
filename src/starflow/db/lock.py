import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class SingletonLock:
    def __init__(self, engine: AsyncEngine, retries: int = 15, delay_sec: float = 1.0) -> None:
        self._engine = engine
        self._retries = retries
        self._delay_sec = delay_sec
        self._connection: AsyncConnection | None = None

    async def acquire(self) -> None:
        for attempt in range(self._retries):
            connection = await self._engine.connect()
            result = await connection.execute(
                text("SELECT pg_try_advisory_lock(hashtext('starflow_singleton'))")
            )
            locked = bool(result.scalar_one())
            if locked:
                self._connection = connection
                return
            await connection.close()
            if attempt < self._retries - 1:
                await asyncio.sleep(self._delay_sec)
        raise RuntimeError("another starflow process holds the singleton lock")

    async def release(self) -> None:
        connection = self._connection
        if connection is None:
            return
        await connection.execute(text("SELECT pg_advisory_unlock(hashtext('starflow_singleton'))"))
        await connection.close()
        self._connection = None
