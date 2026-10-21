from sqlalchemy.ext.asyncio import AsyncEngine

from starflow.db.health import database_ready


class HealthService:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def ready(self) -> bool:
        return await database_ready(self._engine)
