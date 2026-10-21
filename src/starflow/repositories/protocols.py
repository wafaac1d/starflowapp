from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from starflow.domain.records import OutboxJob, User


class UserRepository(Protocol):
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

    async def upsert_telegram(
        self,
        telegram_id: int,
        username: str | None,
        language_code: str | None,
    ) -> User: ...

    async def delete(self, user_id: UUID) -> None: ...

    async def remember_start_param(self, user_id: UUID, start_param: str) -> None: ...

    async def start_param(self, user_id: UUID) -> str | None: ...

    async def ensure_referral_code(self, user_id: UUID) -> str: ...

    async def bind_referrer(self, user_id: UUID, start_param: str | None) -> bool: ...

    async def lock(self, user_id: UUID) -> None: ...


class OutboxRepository(Protocol):
    async def enqueue(
        self,
        user_id: UUID,
        kind: str,
        text_key: str,
        local_date: date,
        scheduled_for: datetime,
    ) -> UUID: ...

    async def claim_due(self, now: datetime, limit: int = 20) -> list[OutboxJob]: ...

    async def mark_sent(self, outbox_id: UUID, sent_at: datetime) -> None: ...

    async def mark_failed(self, outbox_id: UUID, error_name: str, failed_at: datetime) -> None: ...


class UnitOfWork(Protocol):
    users: UserRepository
    outbox: OutboxRepository

    async def commit(self) -> None: ...


UowFactory = Callable[[], "UnitOfWorkContext"]


class UnitOfWorkContext(Protocol):
    users: UserRepository
    outbox: OutboxRepository

    async def __aenter__(self) -> "UnitOfWorkContext": ...

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None: ...

    async def commit(self) -> None: ...
