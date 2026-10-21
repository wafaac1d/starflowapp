from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class SingletonLock:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection | None = None

    async def acquire(self) -> None:
        connection = await self._engine.connect()
        result = await connection.execute(
            text("SELECT pg_try_advisory_lock(hashtext('starflow_singleton'))")
        )
        locked = bool(result.scalar_one())
        if not locked:
            await connection.close()
            raise RuntimeError("another starflow process holds the singleton lock")
        self._connection = connection

    async def release(self) -> None:
        connection = self._connection
        if connection is None:
            return
        await connection.execute(text("SELECT pg_advisory_unlock(hashtext('starflow_singleton'))"))
        await connection.close()
        self._connection = None
