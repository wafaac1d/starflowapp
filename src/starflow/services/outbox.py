from collections.abc import Callable
from types import TracebackType
from typing import Protocol

import structlog

from starflow.domain.time import now_utc
from starflow.i18n.catalog import Catalog
from starflow.repositories.protocols import OutboxRepository


class OutboxStore(Protocol):
    outbox: OutboxRepository

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
    async def send_text(self, telegram_id: int, text: str) -> None: ...


class OutboxService:
    def __init__(self, uow_factory: Callable[[], OutboxWork], catalog: Catalog) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._log = structlog.get_logger("outbox")

    async def dispatch_due(self, sender: TextSender) -> int:
        now = now_utc()
        async with self._uow_factory() as uow:
            jobs = await uow.outbox.claim_due(now)
            await uow.commit()
        delivered = 0
        for job in jobs:
            try:
                await sender.send_text(job.telegram_id, self._catalog.text(job.text_key))
            except Exception as error:
                self._log.warning("outbox_send_failed", error_type=type(error).__name__)
                failed_at = now_utc()
                async with self._uow_factory() as uow:
                    await uow.outbox.mark_failed(job.id, type(error).__name__, failed_at)
                    await uow.commit()
                continue
            sent_at = now_utc()
            async with self._uow_factory() as uow:
                await uow.outbox.mark_sent(job.id, sent_at)
                await uow.commit()
            delivered += 1
        return delivered
