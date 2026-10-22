from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from starflow.repositories.billing import BillingRepository
from starflow.repositories.protocols import OutboxRepository, UserRepository
from starflow.repositories.sql import (
    AiRequestRepository,
    AssistantMessageRepository,
    AuthSessionRepository,
    DailySkyRepository,
    FavoriteRepository,
    ForecastCacheRepository,
    ForecastFeedbackRepository,
    ForecastHistoryRepository,
    GeocodeCacheRepository,
    GiftCodeRepository,
    IdempotencyRepository,
    NotificationSettingsRepository,
    OpsRepository,
    OrderRepository,
    PaymentChargeRepository,
    ProfileRepository,
    RelatedProfileRepository,
    SqlOutboxRepository,
    SqlUserRepository,
    SubscriptionEventRepository,
    SubscriptionRepository,
    UsageCounterRepository,
)


class SqlUnitOfWork:
    users: UserRepository
    profiles: ProfileRepository
    related_profiles: RelatedProfileRepository
    subscriptions: SubscriptionRepository
    subscription_events: SubscriptionEventRepository
    orders: OrderRepository
    charges: PaymentChargeRepository
    usage: UsageCounterRepository
    forecast_cache: ForecastCacheRepository
    forecast_history: ForecastHistoryRepository
    favorites: FavoriteRepository
    notification_settings: NotificationSettingsRepository
    assistant_messages: AssistantMessageRepository
    feedback: ForecastFeedbackRepository
    ai_requests: AiRequestRepository
    geocodes: GeocodeCacheRepository
    daily_sky: DailySkyRepository
    gifts: GiftCodeRepository
    billing: BillingRepository
    idempotency: IdempotencyRepository
    sessions: AuthSessionRepository
    outbox: OutboxRepository
    ops: OpsRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlUnitOfWork":
        session = self._session_factory()
        self._session = session
        self.users = SqlUserRepository(session)
        self.profiles = ProfileRepository(session)
        self.related_profiles = RelatedProfileRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.subscription_events = SubscriptionEventRepository(session)
        self.orders = OrderRepository(session)
        self.charges = PaymentChargeRepository(session)
        self.usage = UsageCounterRepository(session)
        self.forecast_cache = ForecastCacheRepository(session)
        self.forecast_history = ForecastHistoryRepository(session)
        self.favorites = FavoriteRepository(session)
        self.notification_settings = NotificationSettingsRepository(session)
        self.assistant_messages = AssistantMessageRepository(session)
        self.feedback = ForecastFeedbackRepository(session)
        self.ai_requests = AiRequestRepository(session)
        self.geocodes = GeocodeCacheRepository(session)
        self.daily_sky = DailySkyRepository(session)
        self.gifts = GiftCodeRepository(session)
        self.billing = BillingRepository(session)
        self.idempotency = IdempotencyRepository(session)
        self.sessions = AuthSessionRepository(session)
        self.outbox = SqlOutboxRepository(session)
        self.ops = OpsRepository(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        if exc_type is not None:
            await session.rollback()
        await session.close()
        self._session = None

    async def commit(self) -> None:
        await self._require_session().commit()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work is closed")
        return self._session
