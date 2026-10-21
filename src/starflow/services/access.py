from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.repositories.sql import (
    AssistantMessageRepository,
    ForecastHistoryRepository,
    OrderRepository,
)


class AccessStore(Protocol):
    forecast_history: ForecastHistoryRepository
    assistant_messages: AssistantMessageRepository
    orders: OrderRepository


class AccessWork(Protocol):
    async def __aenter__(self) -> AccessStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class AccessService:
    """Чтение чужой истории, переписки и заказа не отличается от отсутствия строки."""

    def __init__(self, uow_factory: Callable[[], AccessWork]) -> None:
        self._uow_factory = uow_factory

    async def owns_history(self, user_id: UUID, history_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            return await uow.forecast_history.owned(user_id, history_id)

    async def owns_message(self, user_id: UUID, message_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            return await uow.assistant_messages.owned(user_id, message_id)

    async def owns_order(self, user_id: UUID, order_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            return await uow.orders.owned(user_id, order_id)
