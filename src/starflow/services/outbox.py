"""Доставка outbox. Резерв и отправка разделены. Exactly-once не обещается.

Захват коммитится до send. Если процесс умер после send и до mark_sent,
истёкшая аренда позволит отправить то же сообщение ещё раз.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID

import structlog

from starflow.domain.errors import DeliveryBlocked, DeliveryRetry
from starflow.domain.time import now_utc
from starflow.i18n.catalog import Catalog
from starflow.repositories.protocols import OutboxRepository, UserRepository
from starflow.services.pace import SendPace


class OutboxStore(Protocol):
    outbox: OutboxRepository
    users: UserRepository

    async def commit(self) -> None: ...


class OutboxWork(Protocol):
    async def __aenter__(self) -> OutboxStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class TextSender(Protocol):
    async def send_notice(self, telegram_id: int, text: str, page: str) -> None: ...


class OutboxService:
    def __init__(
        self,
        uow_factory: Callable[[], OutboxWork],
        catalog: Catalog,
        pace: SendPace | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._pace = pace or SendPace()
        self._log = structlog.get_logger("outbox")

    async def dispatch_due(self, sender: TextSender) -> int:
        now = now_utc()
        async with self._uow_factory() as uow:
            jobs = await uow.outbox.claim_due(now)
            await uow.commit()
        delivered = 0
        for job in jobs:
            await self._pace.wait()
            text = self._catalog.text(job.text_key)
            if job.planet:
                text = self._catalog.format(job.text_key, planet=job.planet)
            try:
                await sender.send_notice(job.telegram_id, text, job.page)
            except DeliveryBlocked as error:
                await self._fail(job.telegram_id, job.id, type(error).__name__, None, blocked=True)
                continue
            except DeliveryRetry as error:
                retry_at = now_utc() + timedelta(seconds=max(error.delay_sec, 1))
                await self._fail(
                    job.telegram_id,
                    job.id,
                    type(error).__name__,
                    retry_at,
                    blocked=False,
                )
                continue
            except Exception as error:
                self._log.warning("outbox_send_failed", error_type=type(error).__name__)
                await self._fail(job.telegram_id, job.id, type(error).__name__, None, blocked=False)
                continue
            sent_at = now_utc()
            async with self._uow_factory() as uow:
                await uow.outbox.mark_sent(job.id, sent_at)
                await uow.commit()
            delivered += 1
        return delivered

    async def _fail(
        self,
        telegram_id: int,
        outbox_id: UUID,
        error_name: str,
        retry_at: datetime | None,
        *,
        blocked: bool,
    ) -> None:
        failed_at = now_utc()
        async with self._uow_factory() as uow:
            if blocked:
                await uow.users.mark_blocked(telegram_id)
            await uow.outbox.mark_failed(outbox_id, error_name, failed_at, retry_at)
            await uow.commit()
