"""Сервис обратной связи и обращений в поддержку."""

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.errors import FieldInvalid
from starflow.domain.support import SupportTicket, support_message_ok, support_subject_ok
from starflow.domain.time import now_utc
from starflow.repositories.sql import SupportRepository


class SupportStore(Protocol):
    support: SupportRepository

    async def commit(self) -> None: ...


class SupportWork(Protocol):
    async def __aenter__(self) -> SupportStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class SupportService:
    def __init__(
        self,
        uow_factory: Callable[[], SupportWork],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or now_utc

    async def create_ticket(
        self,
        user_id: UUID,
        subject: str,
        message: str,
    ) -> SupportTicket:
        cleaned_subject = subject.strip()
        cleaned_message = message.strip()
        if not support_subject_ok(cleaned_subject):
            raise FieldInvalid("subject", "errors.validation")
        if not support_message_ok(cleaned_message):
            raise FieldInvalid("message", "errors.validation")
        now = self._clock()
        async with self._uow_factory() as uow:
            ticket_id = await uow.support.create(
                user_id=user_id,
                subject=cleaned_subject,
                message=cleaned_message,
                now=now,
            )
            await uow.commit()
            created = await uow.support.get(ticket_id)
        if created is None:
            raise FieldInvalid("ticket", "errors.not_found")
        return created

    async def admin_list_tickets(self, is_admin: bool) -> list[SupportTicket]:
        if not is_admin:
            raise FieldInvalid("admin", "errors.unauthorized")
        async with self._uow_factory() as uow:
            return await uow.support.list_all()

    async def admin_close_ticket(self, is_admin: bool, ticket_id: UUID) -> bool:
        if not is_admin:
            raise FieldInvalid("admin", "errors.unauthorized")
        now = self._clock()
        async with self._uow_factory() as uow:
            closed = await uow.support.close(ticket_id, now)
            if closed:
                await uow.commit()
        return closed
