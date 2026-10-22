from collections.abc import Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from starflow.config import Settings
from starflow.logging import get_logger
from starflow.services.billing import BillingService
from starflow.services.ops import OpsService
from starflow.services.outbox import OutboxService, TextSender


class SchedulerRuntime:
    def __init__(
        self,
        settings: Settings,
        outbox: OutboxService,
        sender: TextSender,
        billing: BillingService,
        ops: OpsService,
    ) -> None:
        self._settings = settings
        self._outbox = outbox
        self._sender = sender
        self._billing = billing
        self._ops = ops
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._started = False
        self._log = get_logger("scheduler")

    def start(self) -> None:
        if self._started:
            raise RuntimeError("scheduler is already started")
        self._scheduler.add_job(
            self._tick,
            "interval",
            seconds=self._settings.outbox_interval_sec,
            id="notification_outbox",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._plan,
            "interval",
            minutes=1,
            id="notification_plan",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._warm,
            "interval",
            hours=1,
            id="cache_warmup",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._purge,
            "interval",
            hours=6,
            id="retention",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._maintain,
            "interval",
            minutes=10,
            id="billing_maintain",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        self._scheduler.start()
        self._started = True

    async def shutdown(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=True)
        self._started = False

    async def _tick(self) -> None:
        await self._guard("outbox_tick_failed", self._outbox.dispatch_due(self._sender))

    async def _plan(self) -> None:
        await self._guard("notification_plan_failed", self._ops.plan())

    async def _warm(self) -> None:
        await self._guard("cache_warmup_failed", self._ops.warm())

    async def _purge(self) -> None:
        await self._guard("retention_failed", self._ops.purge())

    async def _maintain(self) -> None:
        await self._guard("billing_maintain_failed", self._billing.maintain())

    async def _guard(self, event: str, work: Awaitable[object]) -> None:
        try:
            await work
        except Exception as error:
            self._log.warning(event, error_type=type(error).__name__)
