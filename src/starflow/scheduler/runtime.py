from apscheduler.schedulers.asyncio import AsyncIOScheduler

from starflow.config import Settings
from starflow.logging import get_logger
from starflow.services.billing import BillingService
from starflow.services.outbox import OutboxService, TextSender


class SchedulerRuntime:
    def __init__(
        self,
        settings: Settings,
        outbox: OutboxService,
        sender: TextSender,
        billing: BillingService,
    ) -> None:
        self._settings = settings
        self._outbox = outbox
        self._sender = sender
        self._billing = billing
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
        )
        self._scheduler.add_job(
            self._maintain,
            "interval",
            minutes=10,
            id="billing_maintain",
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        self._started = True

    async def shutdown(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False

    async def _tick(self) -> None:
        try:
            await self._outbox.dispatch_due(self._sender)
        except Exception as error:
            self._log.warning("outbox_tick_failed", error_type=type(error).__name__)

    async def _maintain(self) -> None:
        try:
            await self._billing.maintain()
        except Exception as error:
            self._log.warning("billing_maintain_failed", error_type=type(error).__name__)
