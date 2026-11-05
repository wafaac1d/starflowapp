"""Доставка outbox. Резерв и отправка разделены. Exactly-once не обещается.

Захват коммитится до send. Если процесс умер после send и до mark_sent,
истёкшая аренда позволит отправить то же сообщение ещё раз.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from types import TracebackType
from typing import Protocol

import structlog

from starflow.domain.errors import DeliveryBlocked, DeliveryRetry
from starflow.domain.records import OutboxJob
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
    async def send_notice(
        self,
        telegram_id: int,
        text: str,
        page: str,
        button_text: str = "",
        previous_message_id: int | None = None,
        buttons: Sequence[tuple[str, str]] = (),
    ) -> int | None: ...


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
        for batch in digest_batches(jobs):
            await self._pace.wait()
            text = "\n\n".join(self._text(job) for job in batch)
            buttons = self._buttons(batch) if len(batch) > 1 else ()
            lone = batch[0]
            button_label = self._catalog.text(lone.button_key) if lone.button_key else ""
            try:
                sent_message_id = await sender.send_notice(
                    lone.telegram_id,
                    text,
                    "" if buttons else lone.page,
                    button_text="" if buttons else button_label,
                    previous_message_id=lone.last_message_id,
                    buttons=buttons,
                )
            except DeliveryBlocked as error:
                await self._fail(batch, type(error).__name__, None, blocked=True)
                continue
            except DeliveryRetry as error:
                retry_at = now_utc() + timedelta(seconds=max(error.delay_sec, 1))
                await self._fail(batch, type(error).__name__, retry_at, blocked=False)
                continue
            except Exception as error:
                self._log.warning("outbox_send_failed", error_type=type(error).__name__)
                await self._fail(batch, type(error).__name__, None, blocked=False)
                continue
            sent_at = now_utc()
            async with self._uow_factory() as uow:
                for job in batch:
                    await uow.outbox.mark_sent(job.id, sent_at)
                if isinstance(sent_message_id, int):
                    await uow.users.update_last_bot_message_id(lone.telegram_id, sent_message_id)
                await uow.commit()
            delivered += 1
        return delivered

    def _text(self, job: OutboxJob) -> str:
        if job.body != "":
            return job.body
        try:
            text = self._catalog.text(job.text_key)
        except KeyError:
            text = self._catalog.text(job.text_key.rsplit("_", 1)[0])
        if job.planet:
            return self._catalog.format(job.text_key, planet=job.planet)
        return text

    def _buttons(self, jobs: Sequence[OutboxJob]) -> tuple[tuple[str, str], ...]:
        found: list[tuple[str, str]] = []
        seen: set[str] = set()
        ordered = sorted(jobs, key=lambda job: _digest_rank(job.kind))
        for job in ordered:
            if job.page == "" or job.page in seen:
                continue
            seen.add(job.page)
            key = job.button_key or _DIGEST_BUTTONS.get(job.kind, "bot.open")
            found.append((self._catalog.text(key), job.page))
        return tuple(found)

    async def _fail(
        self,
        jobs: Sequence[OutboxJob],
        error_name: str,
        retry_at: datetime | None,
        *,
        blocked: bool,
    ) -> None:
        failed_at = now_utc()
        async with self._uow_factory() as uow:
            if blocked and jobs:
                await uow.users.mark_blocked(jobs[0].telegram_id)
            for job in jobs:
                await uow.outbox.mark_failed(job.id, error_name, failed_at, retry_at)
            await uow.commit()


_DIGEST_KINDS = frozenset({"day", "moon", "retro", "affirmation", "tomorrow"})
_DIGEST_ORDER = ("day", "moon", "retro", "affirmation", "tomorrow")
_DIGEST_BUTTONS = {
    "day": "bot.day_button",
    "moon": "bot.moon_button",
    "retro": "bot.retro_button",
    "affirmation": "bot.affirmation_button",
    "tomorrow": "bot.tomorrow_button",
}


def _digest_rank(kind: str) -> int:
    try:
        return _DIGEST_ORDER.index(kind)
    except ValueError:
        return len(_DIGEST_ORDER)


def digest_batches(jobs: Sequence[OutboxJob]) -> list[list[OutboxJob]]:
    """Уведомления одного человека, которые созрели вместе, уходят одним сообщением."""
    batches: list[list[OutboxJob]] = []
    digest_at: dict[int, int] = {}
    for job in jobs:
        if job.kind in _DIGEST_KINDS:
            index = digest_at.get(job.telegram_id)
            if index is None:
                digest_at[job.telegram_id] = len(batches)
                batches.append([job])
            else:
                batches[index].append(job)
            continue
        batches.append([job])
    for batch in batches:
        if len(batch) > 1:
            batch.sort(key=lambda job: _digest_rank(job.kind))
    return batches
