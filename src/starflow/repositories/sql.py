import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, case, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from starflow.db.tables import (
    AiRequestRow,
    AssistantMessageRow,
    AuthSessionRow,
    BroadcastRow,
    BroadcastTargetRow,
    DailySkyRow,
    FavoriteRow,
    ForecastCacheRow,
    ForecastFeedbackRow,
    ForecastHistoryRow,
    GeocodeCacheRow,
    GiftCodeRow,
    IdempotencyKeyRow,
    NotificationOutboxRow,
    NotificationSettingsRow,
    OrderRow,
    PaymentChargeRow,
    ProfileRow,
    RelatedProfileRow,
    StarSpendRow,
    SubscriptionEventRow,
    SubscriptionRow,
    SupportTicketRow,
    UsageCounterRow,
    UserRow,
)
from starflow.domain.broadcast import (
    BROADCAST_BATCH,
    INACTIVE_DAYS,
    TOPUP_DAYS,
    BroadcastJob,
)
from starflow.domain.entitlement import SOURCES, Grant, access_end
from starflow.domain.errors import Conflict, QuotaExceeded
from starflow.domain.notify_clock import LEASE
from starflow.domain.profile import ensure_birth_time
from starflow.domain.records import (
    AdminSnapshot,
    FeedbackCount,
    IdempotencyRecord,
    ModelUsage,
    OpenAccount,
    Order,
    OutboxJob,
    PaymentCharge,
    PlaceHit,
    Profile,
    ProfileDraft,
    RelatedBirth,
    RelatedProfile,
    UsageCounter,
    User,
)
from starflow.domain.retention import (
    AI_DAYS,
    ASSISTANT_DAYS,
    CACHE_DAYS,
    GEOCODE_DAYS,
    HISTORY_DAYS,
    IDEMPOTENCY_DAYS,
    OUTBOX_DAYS,
    cutoff,
)
from starflow.domain.streak import next_streak
from starflow.domain.support import SupportTicket
from starflow.domain.time import now_utc


async def _save(session: AsyncSession, row: object) -> None:
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise Conflict("unique constraint rejected the write") from error
        raise


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(UserRow).where(UserRow.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _user(row)

    async def upsert_telegram(
        self,
        telegram_id: int,
        username: str | None,
        language_code: str | None,
    ) -> User:
        current = await self.get_by_telegram_id(telegram_id)
        if current is None:
            row = UserRow(
                telegram_id=telegram_id,
                username=username,
                language_code=language_code,
            )
            await _save(self._session, row)
            return _user(row)
        stored = await self._session.get(UserRow, current.id)
        if stored is None:
            raise Conflict("user disappeared before update")
        stored.username = username
        stored.language_code = language_code
        stored.updated_at = now_utc()
        await self._session.flush()
        return _user(stored)

    async def mark_bot_welcomed(self, telegram_id: int) -> bool:
        result = await self._session.execute(
            select(UserRow).where(UserRow.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return True
        first_time = not row.bot_welcomed
        if first_time:
            row.bot_welcomed = True
            row.updated_at = now_utc()
            await self._session.flush()
        return first_time

    async def lock(self, user_id: UUID) -> None:
        result = await self._session.execute(
            select(UserRow.id).where(UserRow.id == user_id).with_for_update()
        )
        if result.scalar_one_or_none() is None:
            raise Conflict("user is missing")

    async def remember_start_param(self, user_id: UUID, start_param: str) -> None:
        row = await self._session.get(UserRow, user_id)
        if row is None:
            raise Conflict("user disappeared before the start parameter was stored")
        row.pending_start_param = start_param
        row.updated_at = now_utc()
        await self._session.flush()

    async def start_param(self, user_id: UUID) -> str | None:
        row = await self._session.get(UserRow, user_id)
        if row is None:
            return None
        return row.pending_start_param

    async def ensure_referral_code(self, user_id: UUID) -> str:
        row = await self._session.get(UserRow, user_id)
        if row is None:
            raise Conflict("user is missing")
        if row.referral_code:
            return row.referral_code
        row.referral_code = secrets.token_hex(8)
        row.updated_at = now_utc()
        await self._session.flush()
        return row.referral_code

    async def bind_referrer(self, user_id: UUID, start_param: str | None) -> bool:
        if start_param is None or not start_param.startswith("ref_"):
            return False
        code = start_param.removeprefix("ref_")
        owner = await self._session.get(UserRow, user_id)
        if owner is None or owner.referral_code == code or owner.referred_by is not None:
            return False
        result = await self._session.execute(select(UserRow).where(UserRow.referral_code == code))
        referrer = result.scalar_one_or_none()
        if referrer is None or referrer.id == user_id:
            return False
        owner.referred_by = referrer.id
        owner.updated_at = now_utc()
        await self._session.flush()
        return True

    async def delete(self, user_id: UUID) -> None:
        charges = await self._session.execute(
            select(PaymentChargeRow).where(PaymentChargeRow.user_id == user_id)
        )
        for charge in charges.scalars():
            charge.provider_payload = {
                "currency": charge.currency,
                "amount_stars": charge.amount_stars,
            }
        orders = await self._session.execute(select(OrderRow).where(OrderRow.user_id == user_id))
        for order in orders.scalars():
            order.invoice_link = None
        await self._session.flush()
        row = await self._session.get(UserRow, user_id)
        if row is None:
            return
        row.username = None
        row.pending_start_param = None
        await self._session.delete(row)
        await self._session.flush()

    async def mark_blocked(self, telegram_id: int) -> None:
        result = await self._session.execute(
            select(UserRow).where(UserRow.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.is_blocked = True
        row.updated_at = now_utc()
        await self._session.flush()


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, user_id: UUID, draft: ProfileDraft) -> Profile:
        ensure_birth_time(draft.birth_time, draft.birth_time_unknown)
        result = await self._session.execute(
            select(ProfileRow).where(ProfileRow.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ProfileRow(
                user_id=user_id, display_name=draft.display_name, timezone=draft.timezone
            )
            self._session.add(row)
        _apply_profile(row, draft)
        await self._session.flush()
        return _profile(row)

    async def get_by_user_id(self, user_id: UUID) -> Profile | None:
        result = await self._session.execute(
            select(ProfileRow).where(ProfileRow.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _profile(row)

    async def ensure(self, user_id: UUID) -> Profile:
        current = await self.get_by_user_id(user_id)
        if current is not None:
            return current
        row = ProfileRow(user_id=user_id, onboarding_step="welcome", birth_time_unknown=False)
        self._session.add(row)
        await self._session.flush()
        return _profile(row)

    async def save_onboarding(
        self,
        user_id: UUID,
        *,
        step: str,
        display_name: str | None = None,
        birth_date: date | None = None,
        birth_time: time | None = None,
        birth_time_unknown: bool | None = None,
        timezone: str | None = None,
        clear_time: bool = False,
        clear_place: bool = False,
    ) -> Profile:
        row = await self._row(user_id)
        row.onboarding_step = step
        if display_name is not None:
            row.display_name = display_name
        date_changed = birth_date is not None and row.birth_date != birth_date
        if birth_date is not None:
            row.birth_date = birth_date
        if birth_time_unknown is not None:
            row.birth_time_unknown = birth_time_unknown
        if clear_time:
            row.birth_time = None
        elif birth_time is not None:
            row.birth_time = birth_time
        if timezone is not None:
            row.timezone = timezone
        if clear_place:
            row.birth_place = None
            row.latitude = None
            row.longitude = None
        row.updated_at = now_utc()
        await self._session.flush()
        if (
            birth_date is not None
            or birth_time is not None
            or birth_time_unknown is not None
            or timezone is not None
            or clear_time
            or clear_place
        ):
            await _drop_natal_cache(self._session, user_id)
        if date_changed:
            await _drop_natal_spend(self._session, user_id)
        return _profile(row)

    async def save_place(
        self,
        user_id: UUID,
        label: str,
        latitude: Decimal,
        longitude: Decimal,
        timezone: str,
    ) -> Profile:
        row = await self._row(user_id)
        row.birth_place = label
        row.latitude = latitude
        row.longitude = longitude
        row.timezone = timezone
        row.onboarding_step = "done"
        row.updated_at = now_utc()
        await self._session.flush()
        await _drop_natal_cache(self._session, user_id)
        return _profile(row)

    async def touch_streak(self, user_id: UUID, today: date) -> int:
        row = await self._row(user_id)
        row.streak_count = next_streak(row.streak_last_date, today, row.streak_count)
        row.streak_last_date = today
        row.updated_at = now_utc()
        await self._session.flush()
        return row.streak_count

    async def _row(self, user_id: UUID) -> ProfileRow:
        result = await self._session.execute(
            select(ProfileRow).where(ProfileRow.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise Conflict("profile is missing")
        return row


class RelatedProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, owner_user_id: UUID, draft: ProfileDraft, *, consent: bool = False) -> UUID:
        ensure_birth_time(draft.birth_time, draft.birth_time_unknown)
        row = RelatedProfileRow(
            owner_user_id=owner_user_id,
            display_name=draft.display_name,
            timezone=draft.timezone,
            consent=consent,
        )
        _apply_related(row, draft)
        await _save(self._session, row)
        return row.id

    async def count_for_owner(self, owner_user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(RelatedProfileRow)
            .where(RelatedProfileRow.owner_user_id == owner_user_id)
        )
        return int(result.scalar_one())

    async def list_births(self, owner_user_id: UUID) -> tuple[RelatedBirth, ...]:
        result = await self._session.execute(
            select(RelatedProfileRow).where(RelatedProfileRow.owner_user_id == owner_user_id)
        )
        return tuple(
            RelatedBirth(
                id=row.id,
                display_name=row.display_name,
                birth_date=row.birth_date,
                consent=row.consent,
                birth_time=row.birth_time,
                birth_time_unknown=row.birth_time_unknown,
            )
            for row in result.scalars()
        )

    async def get_owned(self, owner_user_id: UUID, related_id: UUID) -> RelatedProfile | None:
        row = await self._session.get(RelatedProfileRow, related_id)
        if row is None or row.owner_user_id != owner_user_id:
            return None
        return RelatedProfile(
            id=row.id,
            display_name=row.display_name,
            birth_date=row.birth_date,
            birth_time_unknown=row.birth_time_unknown,
            birth_place=row.birth_place,
            latitude=row.latitude,
            longitude=row.longitude,
            consent=row.consent,
        )

    async def set_consent(self, owner_user_id: UUID, related_id: UUID, consent: bool) -> bool:
        row = await self._session.get(RelatedProfileRow, related_id)
        if row is None or row.owner_user_id != owner_user_id:
            return False
        row.consent = consent
        await self._session.flush()
        return True

    async def delete_owned(self, owner_user_id: UUID, related_id: UUID) -> bool:
        row = await self._session.get(RelatedProfileRow, related_id)
        if row is None or row.owner_user_id != owner_user_id:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: UUID,
        plan_code: str,
        status: str,
        period_start: datetime,
        period_end: datetime,
        source: str,
        *,
        grace_until: datetime | None = None,
        revoked_at: datetime | None = None,
    ) -> UUID:
        row = SubscriptionRow(
            user_id=user_id,
            plan_code=plan_code,
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
            grace_until=grace_until,
            revoked_at=revoked_at,
            source=source,
        )
        await _save(self._session, row)
        return row.id

    async def list_for_user(self, user_id: UUID) -> tuple[Grant, ...]:
        result = await self._session.execute(
            select(SubscriptionRow).where(SubscriptionRow.user_id == user_id)
        )
        return tuple(_grant(row) for row in result.scalars())

    async def revoke(self, grant_id: UUID, revoked_at: datetime) -> None:
        row = await self._session.get(SubscriptionRow, grant_id)
        if row is None:
            raise Conflict("grant is missing")
        row.status = "revoked"
        row.revoked_at = revoked_at
        await self._session.flush()

    async def has_active(self, user_id: UUID, now: datetime) -> bool:
        grants = await self.list_for_user(user_id)
        return access_end(grants, now) is not None

    async def premium_user_ids(self, now: datetime) -> set[UUID]:
        result = await self._session.execute(_open_premium(now).distinct())
        return set(result.scalars())


class SubscriptionEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        subscription_id: UUID,
        user_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> UUID:
        row = SubscriptionEventRow(
            subscription_id=subscription_id,
            user_id=user_id,
            event_type=event_type,
            payload=payload,
        )
        await _save(self._session, row)
        return row.id


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: UUID | None,
        plan_code: str,
        amount_stars: int,
        currency: str,
        status: str,
        invoice_payload: str,
    ) -> Order:
        row = OrderRow(
            user_id=user_id,
            plan_code=plan_code,
            amount_stars=amount_stars,
            currency=currency,
            status=status,
            invoice_payload=invoice_payload,
        )
        await _save(self._session, row)
        return Order(id=row.id, user_id=row.user_id, invoice_payload=row.invoice_payload)

    async def get(self, order_id: UUID) -> Order | None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            return None
        return Order(id=row.id, user_id=row.user_id, invoice_payload=row.invoice_payload)

    async def owned(self, user_id: UUID, order_id: UUID) -> bool:
        row = await self._session.get(OrderRow, order_id)
        return row is not None and row.user_id == user_id


class PaymentChargeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        order_id: UUID,
        user_id: UUID | None,
        telegram_payment_charge_id: str,
        amount_stars: int,
        currency: str,
        period_start: datetime,
        period_end: datetime,
        charged_at: datetime,
        provider_payload: dict[str, object],
    ) -> PaymentCharge:
        row = PaymentChargeRow(
            order_id=order_id,
            user_id=user_id,
            telegram_payment_charge_id=telegram_payment_charge_id,
            amount_stars=amount_stars,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
            charged_at=charged_at,
            provider_payload=provider_payload,
        )
        await _save(self._session, row)
        return _charge(row)

    async def get(self, charge_id: UUID) -> PaymentCharge | None:
        row = await self._session.get(PaymentChargeRow, charge_id)
        if row is None:
            return None
        return _charge(row)


class UsageCounterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def open_counter(
        self,
        user_id: UUID,
        counter_key: str,
        period_start: datetime,
        period_end: datetime,
        quota_limit: int,
    ) -> UsageCounter:
        row = UsageCounterRow(
            user_id=user_id,
            counter_key=counter_key,
            period_start=period_start,
            period_end=period_end,
            used=0,
            reserved=0,
            quota_limit=quota_limit,
        )
        await _save(self._session, row)
        return _counter(row)

    async def find(
        self,
        user_id: UUID,
        counter_key: str,
        period_start: datetime,
    ) -> UsageCounter | None:
        return await self._window(user_id, counter_key, period_start, lock=False)

    async def lock_window(
        self,
        user_id: UUID,
        counter_key: str,
        period_start: datetime,
    ) -> UsageCounter | None:
        return await self._window(user_id, counter_key, period_start, lock=True)

    async def get(self, counter_id: UUID) -> UsageCounter | None:
        row = await self._session.get(UsageCounterRow, counter_id)
        if row is None:
            return None
        return _counter(row)

    async def change(
        self,
        counter_id: UUID,
        *,
        used_delta: int,
        reserved_delta: int,
    ) -> UsageCounter:
        result = await self._session.execute(
            select(UsageCounterRow).where(UsageCounterRow.id == counter_id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise Conflict("usage counter is missing")
        used = row.used + used_delta
        reserved = row.reserved + reserved_delta
        if used < 0 or reserved < 0 or used + reserved > row.quota_limit:
            raise QuotaExceeded("usage counter is exhausted")
        row.used = used
        row.reserved = reserved
        await self._session.flush()
        return _counter(row)

    async def increment(self, counter_id: UUID) -> UsageCounter:
        return await self.change(counter_id, used_delta=1, reserved_delta=0)

    async def _window(
        self,
        user_id: UUID,
        counter_key: str,
        period_start: datetime,
        *,
        lock: bool,
    ) -> UsageCounter | None:
        query = select(UsageCounterRow).where(
            UsageCounterRow.user_id == user_id,
            UsageCounterRow.counter_key == counter_key,
            UsageCounterRow.period_start == period_start,
        )
        if lock:
            query = query.with_for_update()
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _counter(row)


class ForecastCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def put(
        self,
        cache_key: str,
        user_id: UUID | None,
        kind: str,
        payload: dict[str, object],
        valid_until: datetime,
    ) -> UUID:
        row = ForecastCacheRow(
            cache_key=cache_key,
            user_id=user_id,
            kind=kind,
            payload=payload,
            valid_until=valid_until,
        )
        await _save(self._session, row)
        return row.id

    async def peek(self, cache_key: str, now: datetime) -> bool:
        result = await self._session.execute(
            select(ForecastCacheRow.valid_until).where(ForecastCacheRow.cache_key == cache_key)
        )
        until = result.scalar_one_or_none()
        return until is not None and until > now

    async def get(self, cache_key: str) -> dict[str, object] | None:
        result = await self._session.execute(
            select(ForecastCacheRow).where(ForecastCacheRow.cache_key == cache_key)
        )
        row = result.scalar_one_or_none()
        if row is None or row.valid_until <= now_utc():
            return None
        return _object_dict(row.payload)

    async def lock(self, cache_key: str) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:cache_key))"),
            {"cache_key": cache_key},
        )

    async def read_fresh(
        self,
        cache_key: str,
        now: datetime,
    ) -> tuple[dict[str, object], datetime] | None:
        result = await self._session.execute(
            select(ForecastCacheRow)
            .where(ForecastCacheRow.cache_key == cache_key)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.valid_until <= now:
            return None
        row.hits += 1
        await self._session.flush()
        return _object_dict(row.payload), row.valid_until

    async def write_shared(
        self,
        cache_key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> tuple[dict[str, object], datetime]:
        result = await self._session.execute(
            select(ForecastCacheRow).where(ForecastCacheRow.cache_key == cache_key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ForecastCacheRow(
                cache_key=cache_key,
                user_id=None,
                kind=kind,
                payload=payload,
                valid_until=expires_at,
                hits=0,
            )
            await _save(self._session, row)
            return payload, expires_at
        row.user_id = None
        row.kind = kind
        row.payload = payload
        row.valid_until = expires_at
        row.hits = 0
        await self._session.flush()
        return payload, expires_at

    async def overwrite(
        self,
        cache_key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> tuple[dict[str, object], datetime]:
        result = await self._session.execute(
            select(ForecastCacheRow).where(ForecastCacheRow.cache_key == cache_key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return await self.write_shared(cache_key, kind, payload, expires_at)
        row.kind = kind
        row.payload = payload
        row.valid_until = expires_at
        await self._session.flush()
        return payload, expires_at

    async def delete_kind(self, user_id: UUID, kind: str) -> None:
        await self._session.execute(
            delete(ForecastCacheRow).where(
                ForecastCacheRow.user_id == user_id,
                ForecastCacheRow.kind == kind,
            )
        )


class ForecastHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: UUID,
        kind: str,
        period_date: date,
        payload: dict[str, object],
    ) -> UUID:
        row = ForecastHistoryRow(
            user_id=user_id,
            kind=kind,
            period_date=period_date,
            payload=payload,
        )
        await _save(self._session, row)
        return row.id

    async def update_payload(self, history_id: UUID, payload: dict[str, object]) -> None:
        row = await self._session.get(ForecastHistoryRow, history_id)
        if row is not None:
            row.payload = payload
            await self._session.flush()

    async def owned(self, user_id: UUID, history_id: UUID) -> bool:
        row = await self._session.get(ForecastHistoryRow, history_id)
        return row is not None and row.user_id == user_id

    async def find(
        self,
        user_id: UUID,
        kind: str,
        period_date: date,
    ) -> tuple[UUID, dict[str, object]] | None:
        result = await self._session.execute(
            select(ForecastHistoryRow).where(
                ForecastHistoryRow.user_id == user_id,
                ForecastHistoryRow.kind == kind,
                ForecastHistoryRow.period_date == period_date,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return row.id, _object_dict(row.payload)

    async def payload_for(self, user_id: UUID, history_id: UUID) -> dict[str, object] | None:
        row = await self._session.get(ForecastHistoryRow, history_id)
        if row is None or row.user_id != user_id:
            return None
        return _object_dict(row.payload)

    async def list_for_user(self, user_id: UUID) -> tuple[ForecastHistoryRow, ...]:
        result = await self._session.execute(
            select(ForecastHistoryRow)
            .where(ForecastHistoryRow.user_id == user_id)
            .order_by(ForecastHistoryRow.created_at.desc())
        )
        return tuple(result.scalars())


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: UUID, target_type: str, target_id: UUID) -> UUID:
        row = FavoriteRow(user_id=user_id, target_type=target_type, target_id=target_id)
        await _save(self._session, row)
        return row.id

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(FavoriteRow).where(FavoriteRow.user_id == user_id)
        )
        return int(result.scalar_one())

    async def list_for_user(self, user_id: UUID) -> tuple[FavoriteRow, ...]:
        result = await self._session.execute(
            select(FavoriteRow)
            .where(FavoriteRow.user_id == user_id)
            .order_by(FavoriteRow.created_at.desc())
        )
        return tuple(result.scalars())


class NotificationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        user_id: UUID,
        digest_enabled: bool,
        digest_local_time: time,
        timezone: str,
    ) -> None:
        row = await self._session.get(NotificationSettingsRow, user_id)
        if row is None:
            await _save(
                self._session,
                NotificationSettingsRow(
                    user_id=user_id,
                    digest_enabled=digest_enabled,
                    digest_local_time=digest_local_time,
                    timezone=timezone,
                ),
            )
            return
        row.digest_enabled = digest_enabled
        row.digest_local_time = digest_local_time
        row.timezone = timezone
        row.updated_at = now_utc()
        await self._session.flush()

    async def save_preferences(
        self,
        user_id: UUID,
        local_time: time,
        timezone: str,
        *,
        day: bool,
        moon: bool,
        retro: bool,
    ) -> None:
        row = await self._session.get(NotificationSettingsRow, user_id)
        enabled = day or moon or retro
        if row is None:
            await _save(
                self._session,
                NotificationSettingsRow(
                    user_id=user_id,
                    digest_enabled=enabled,
                    digest_local_time=local_time,
                    timezone=timezone,
                    day_enabled=day,
                    moon_enabled=moon,
                    retro_enabled=retro,
                ),
            )
            return
        row.digest_enabled = enabled
        row.digest_local_time = local_time
        row.timezone = timezone
        row.day_enabled = day
        row.moon_enabled = moon
        row.retro_enabled = retro
        row.updated_at = now_utc()
        await self._session.flush()

    async def read(self, user_id: UUID) -> NotificationSettingsRow | None:
        return await self._session.get(NotificationSettingsRow, user_id)

    async def enabled(self) -> list[NotificationSettingsRow]:
        result = await self._session.execute(
            select(NotificationSettingsRow).where(
                or_(
                    NotificationSettingsRow.day_enabled.is_(True),
                    NotificationSettingsRow.moon_enabled.is_(True),
                    NotificationSettingsRow.retro_enabled.is_(True),
                )
            )
        )
        return list(result.scalars())


class AssistantMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: UUID,
        role: str,
        content: str,
        period_start: datetime,
    ) -> UUID:
        row = AssistantMessageRow(
            user_id=user_id,
            role=role,
            content=content,
            period_start=period_start,
        )
        await _save(self._session, row)
        return row.id

    async def owned(self, user_id: UUID, message_id: UUID) -> bool:
        row = await self._session.get(AssistantMessageRow, message_id)
        return row is not None and row.user_id == user_id

    async def recent(
        self,
        user_id: UUID,
        limit: int,
        before: datetime | None,
    ) -> tuple[tuple[UUID, datetime, str, str], ...]:
        statement = (
            select(AssistantMessageRow)
            .where(AssistantMessageRow.user_id == user_id)
            .order_by(AssistantMessageRow.created_at.desc())
            .limit(limit)
        )
        if before is not None:
            statement = statement.where(AssistantMessageRow.created_at < before)
        result = await self._session.execute(statement)
        rows = list(result.scalars())
        rows.reverse()
        return tuple((row.id, row.created_at, row.role, row.content) for row in rows)


class ForecastFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: UUID,
        forecast_history_id: UUID,
        score: int,
        comment: str | None,
    ) -> UUID:
        if score < 1 or score > 5:
            raise ValueError("feedback score is outside 1..5")
        row = ForecastFeedbackRow(
            user_id=user_id,
            forecast_history_id=forecast_history_id,
            score=score,
            comment=comment,
        )
        await _save(self._session, row)
        return row.id


class AiRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: UUID | None,
        model: str,
        purpose: str,
        status: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        latency_ms: int | None = None,
        error_code: str | None = None,
    ) -> UUID:
        row = AiRequestRow(
            user_id=user_id,
            model=model,
            purpose=purpose,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            error_code=error_code,
        )
        await _save(self._session, row)
        return row.id


class GeocodeCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def put(
        self,
        query_normalized: str,
        latitude: Decimal,
        longitude: Decimal,
        display_name: str,
        provider_payload: dict[str, object],
    ) -> UUID:
        row = GeocodeCacheRow(
            query_normalized=query_normalized,
            latitude=latitude,
            longitude=longitude,
            display_name=display_name,
            provider_payload=provider_payload,
        )
        await _save(self._session, row)
        return row.id

    async def get_results(self, query_normalized: str) -> list[PlaceHit] | None:
        result = await self._session.execute(
            select(GeocodeCacheRow).where(GeocodeCacheRow.query_normalized == query_normalized)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _place_hits(row)

    async def store_results(self, query_normalized: str, hits: list[PlaceHit]) -> None:
        if not hits:
            return
        result = await self._session.execute(
            select(GeocodeCacheRow).where(GeocodeCacheRow.query_normalized == query_normalized)
        )
        row = result.scalar_one_or_none()
        payload: dict[str, object] = {
            "results": [
                {
                    "label": hit.label,
                    "latitude": str(hit.latitude),
                    "longitude": str(hit.longitude),
                }
                for hit in hits
            ]
        }
        first = hits[0]
        if row is None:
            await self.put(query_normalized, first.latitude, first.longitude, first.label, payload)
            return
        row.latitude = first.latitude
        row.longitude = first.longitude
        row.display_name = first.label
        row.provider_payload = payload
        await self._session.flush()


class DailySkyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def put(self, sky_date: date, payload: dict[str, object], computed_at: datetime) -> UUID:
        row = DailySkyRow(sky_date=sky_date, payload=payload, computed_at=computed_at)
        await _save(self._session, row)
        return row.id

    async def get(self, sky_date: date) -> dict[str, object] | None:
        result = await self._session.execute(
            select(DailySkyRow).where(DailySkyRow.sky_date == sky_date)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _object_dict(row.payload)


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        result = await self._session.execute(
            select(IdempotencyKeyRow)
            .where(
                IdempotencyKeyRow.user_id == user_id,
                IdempotencyKeyRow.idempotency_key == key,
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _idempotency(row)

    async def count_reserved(self, user_id: UUID, feature: str) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(IdempotencyKeyRow)
            .where(
                IdempotencyKeyRow.user_id == user_id,
                IdempotencyKeyRow.feature == feature,
                IdempotencyKeyRow.status == "reserved",
            )
        )
        return int(result.scalar_one())

    async def hold(
        self,
        user_id: UUID,
        key: str,
        feature: str,
        marker: dict[str, object],
        existing: IdempotencyRecord | None,
    ) -> None:
        if existing is None:
            await _save(
                self._session,
                IdempotencyKeyRow(
                    user_id=user_id,
                    idempotency_key=key,
                    feature=feature,
                    status="reserved",
                    result=marker,
                ),
            )
            return
        row = await self._session.get(IdempotencyKeyRow, existing.id)
        if row is None:
            raise Conflict("idempotency key is missing")
        row.feature = feature
        row.status = "reserved"
        row.result = marker
        await self._session.flush()

    async def complete(self, record_id: UUID, result: dict[str, object]) -> None:
        row = await self._session.get(IdempotencyKeyRow, record_id)
        if row is None or row.status != "reserved":
            raise Conflict("idempotency reservation is missing")
        row.status = "committed"
        row.result = result
        await self._session.flush()

    async def mark_released(self, record_id: UUID) -> None:
        row = await self._session.get(IdempotencyKeyRow, record_id)
        if row is None or row.status != "reserved":
            return
        row.status = "released"
        row.result = None
        await self._session.flush()


class GiftCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        code: str,
        purchaser_user_id: UUID | None,
        plan_code: str,
        status: str,
        charge_id: UUID | None = None,
    ) -> UUID:
        row = GiftCodeRow(
            code=code,
            purchaser_user_id=purchaser_user_id,
            plan_code=plan_code,
            status=status,
            charge_id=charge_id,
        )
        await _save(self._session, row)
        return row.id


class AuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        await _save(
            self._session,
            AuthSessionRow(user_id=user_id, token_hash=token_hash, expires_at=expires_at),
        )

    async def find_user(self, token_hash: str, now: datetime) -> User | None:
        result = await self._session.execute(
            select(UserRow)
            .join(AuthSessionRow, AuthSessionRow.user_id == UserRow.id)
            .where(
                AuthSessionRow.token_hash == token_hash,
                AuthSessionRow.revoked_at.is_(None),
                AuthSessionRow.expires_at > now,
                UserRow.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _user(row)

    async def revoke(self, token_hash: str, now: datetime) -> None:
        result = await self._session.execute(
            select(AuthSessionRow).where(AuthSessionRow.token_hash == token_hash)
        )
        row = result.scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return
        row.revoked_at = now
        await self._session.flush()


class SqlOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        user_id: UUID,
        kind: str,
        text_key: str,
        local_date: date,
        scheduled_for: datetime,
        event_key: str | None = None,
        page: str = "",
        planet: str = "",
        body: str = "",
    ) -> UUID:
        row = NotificationOutboxRow(
            user_id=user_id,
            kind=kind,
            event_key=event_key or local_date.isoformat(),
            payload={"text_key": text_key, "page": page, "planet": planet, "body": body},
            local_date=local_date,
            status="pending",
            attempts=0,
            scheduled_for=scheduled_for,
        )
        await _save(self._session, row)
        return row.id

    async def claim_due(self, now: datetime, limit: int = 25) -> list[OutboxJob]:
        stale = now - timedelta(minutes=5)
        statement = text(
            """
            UPDATE notification_outbox AS o
            SET status = 'reserved',
                leased_until = :lease,
                attempts = o.attempts + 1,
                updated_at = :now
            FROM users AS u
            WHERE u.id = o.user_id
              AND o.id IN (
                SELECT o2.id
                FROM notification_outbox AS o2
                JOIN users AS u2 ON u2.id = o2.user_id
                WHERE u2.is_blocked = false
                  AND u2.deleted_at IS NULL
                  AND (
                    (o2.status = 'pending' AND o2.scheduled_for <= :now)
                    OR (
                      o2.status IN ('reserved', 'sending')
                      AND o2.leased_until IS NOT NULL
                      AND o2.leased_until <= :now
                    )
                    OR (
                      o2.status = 'sending'
                      AND o2.leased_until IS NULL
                      AND o2.updated_at <= :stale
                    )
                  )
                ORDER BY o2.scheduled_for
                LIMIT :limit
                FOR UPDATE OF o2 SKIP LOCKED
              )
            RETURNING o.id, u.telegram_id, o.payload
            """
        )
        rows = await self._session.execute(
            statement,
            {"now": now, "lease": now + LEASE, "stale": stale, "limit": limit},
        )
        jobs: list[OutboxJob] = []
        for item in rows.mappings():
            payload = item["payload"]
            if not isinstance(payload, dict):
                continue
            text_key = payload.get("text_key")
            page = payload.get("page")
            planet = payload.get("planet")
            body = payload.get("body")
            if not isinstance(text_key, str) or text_key == "":
                continue
            jobs.append(
                OutboxJob(
                    id=item["id"],
                    telegram_id=int(item["telegram_id"]),
                    text_key=text_key,
                    page=page if isinstance(page, str) else "",
                    planet=planet if isinstance(planet, str) else "",
                    body=body if isinstance(body, str) else "",
                )
            )
        await self._session.flush()
        return jobs

    async def mark_sent(self, outbox_id: UUID, sent_at: datetime) -> None:
        row = await self._session.get(NotificationOutboxRow, outbox_id)
        if row is None:
            raise Conflict("outbox row is missing")
        if row.status == "sent":
            return
        row.status = "sent"
        row.sent_at = sent_at
        row.leased_until = None
        row.updated_at = sent_at
        row.last_error = None
        await self._session.flush()

    async def mark_failed(
        self,
        outbox_id: UUID,
        error_name: str,
        failed_at: datetime,
        retry_at: datetime | None = None,
    ) -> None:
        row = await self._session.get(NotificationOutboxRow, outbox_id)
        if row is None:
            raise Conflict("outbox row is missing")
        if row.status == "sent":
            return
        terminal = error_name == "DeliveryBlocked" or (retry_at is None and row.attempts >= 5)
        row.status = "failed" if terminal else "pending"
        if not terminal:
            row.scheduled_for = retry_at or (failed_at + timedelta(seconds=30 * row.attempts))
        row.leased_until = None
        row.last_error = error_name[:200]
        row.updated_at = failed_at
        row.sent_at = None
        await self._session.flush()


class OpsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def purge(self, now: datetime) -> None:
        await self._session.execute(
            delete(ForecastCacheRow).where(ForecastCacheRow.valid_until < cutoff(now, CACHE_DAYS))
        )
        await self._session.execute(
            delete(ForecastHistoryRow).where(
                ForecastHistoryRow.created_at < cutoff(now, HISTORY_DAYS)
            )
        )
        await self._session.execute(
            delete(AiRequestRow).where(AiRequestRow.created_at < cutoff(now, AI_DAYS))
        )
        await self._session.execute(
            delete(NotificationOutboxRow).where(
                NotificationOutboxRow.status.in_(("sent", "failed")),
                NotificationOutboxRow.updated_at < cutoff(now, OUTBOX_DAYS),
            )
        )
        await self._session.execute(
            delete(IdempotencyKeyRow).where(
                IdempotencyKeyRow.status == "committed",
                IdempotencyKeyRow.created_at < cutoff(now, IDEMPOTENCY_DAYS),
            )
        )
        await self._session.execute(
            delete(AssistantMessageRow).where(
                AssistantMessageRow.created_at < cutoff(now, ASSISTANT_DAYS)
            )
        )
        await self._session.execute(
            delete(GeocodeCacheRow).where(GeocodeCacheRow.created_at < cutoff(now, GEOCODE_DAYS))
        )
        await self._session.flush()

    async def snapshot(self, start: datetime, end: datetime) -> AdminSnapshot:
        active = await self._session.scalar(
            select(func.count(func.distinct(ForecastHistoryRow.user_id))).where(
                ForecastHistoryRow.created_at >= start,
                ForecastHistoryRow.created_at < end,
            )
        )
        accounts = await self._session.scalar(
            select(func.count()).select_from(UserRow).where(UserRow.deleted_at.is_(None))
        )
        payments = await self._session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(PaymentChargeRow.amount_stars), 0),
            ).where(PaymentChargeRow.charged_at >= start, PaymentChargeRow.charged_at < end)
        )
        payment_count, stars = payments.one()
        refunds = await self._session.scalar(
            select(func.count())
            .select_from(PaymentChargeRow)
            .where(
                PaymentChargeRow.refunded_at.is_not(None),
                PaymentChargeRow.refunded_at >= start,
                PaymentChargeRow.refunded_at < end,
            )
        )
        source_rows = await self._session.execute(
            select(SubscriptionRow.source, func.count())
            .where(
                SubscriptionRow.current_period_start < end,
                SubscriptionRow.current_period_end > start,
            )
            .group_by(SubscriptionRow.source)
        )
        model_rows = await self._session.execute(
            select(
                AiRequestRow.model,
                func.count(),
                func.coalesce(func.sum(AiRequestRow.prompt_tokens), 0),
                func.coalesce(func.sum(AiRequestRow.completion_tokens), 0),
                func.count().filter(AiRequestRow.status != "ok"),
                func.percentile_cont(0.5).within_group(AiRequestRow.latency_ms),
            )
            .where(AiRequestRow.created_at >= start, AiRequestRow.created_at < end)
            .group_by(AiRequestRow.model)
        )
        cache = await self._session.execute(
            select(func.count(), func.coalesce(func.sum(ForecastCacheRow.hits), 0)).where(
                ForecastCacheRow.created_at >= start,
                ForecastCacheRow.created_at < end,
            )
        )
        cache_rows, cache_hits = cache.one()
        version = func.coalesce(ForecastHistoryRow.payload["prompt_version"].astext, "")
        feedback_rows = await self._session.execute(
            select(ForecastHistoryRow.kind, version, func.count())
            .select_from(ForecastFeedbackRow)
            .join(
                ForecastHistoryRow,
                ForecastHistoryRow.id == ForecastFeedbackRow.forecast_history_id,
            )
            .where(ForecastFeedbackRow.created_at >= start, ForecastFeedbackRow.created_at < end)
            .group_by(ForecastHistoryRow.kind, version)
        )
        loaded_models = model_rows.all()
        return AdminSnapshot(
            active_users=int(active or 0),
            open_accounts=int(accounts or 0),
            payments=int(payment_count or 0),
            stars=int(stars or 0),
            refunds=int(refunds or 0),
            sources=tuple((str(source), int(count)) for source, count in source_rows.all()),
            models=tuple(
                ModelUsage(
                    str(model),
                    int(calls),
                    int(prompt_tokens),
                    int(completion_tokens),
                    int(errors),
                    None if latency is None else int(latency),
                )
                for model, calls, prompt_tokens, completion_tokens, errors, latency in loaded_models
            ),
            cache_rows=int(cache_rows or 0),
            cache_hits=int(cache_hits or 0),
            feedback=tuple(
                FeedbackCount(str(kind), str(prompt_version), int(count))
                for kind, prompt_version, count in feedback_rows.all()
            ),
        )

    async def count_open_accounts(self) -> int:
        counted = await self._session.scalar(
            select(func.count()).select_from(UserRow).where(UserRow.deleted_at.is_(None))
        )
        return int(counted or 0)

    async def open_accounts(self, limit: int, offset: int) -> tuple[OpenAccount, ...]:
        result = await self._session.execute(
            select(
                UserRow.id,
                UserRow.telegram_id,
                UserRow.username,
                ProfileRow.display_name,
            )
            .outerjoin(ProfileRow, ProfileRow.user_id == UserRow.id)
            .where(UserRow.deleted_at.is_(None))
            .order_by(UserRow.created_at.desc(), UserRow.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return tuple(
            OpenAccount(
                user_id=user_id,
                telegram_id=int(telegram_id),
                username=username,
                display_name=display_name,
            )
            for user_id, telegram_id, username, display_name in result.all()
        )

    async def insert_broadcast(self, body: str, audience: str, now: datetime) -> UUID:
        row = BroadcastRow(
            body=body,
            audience=audience,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        await _save(self._session, row)
        return row.id

    async def next_queued_broadcast(self) -> BroadcastJob | None:
        result = await self._session.execute(
            select(BroadcastRow)
            .where(BroadcastRow.status == "queued")
            .order_by(BroadcastRow.created_at, BroadcastRow.id)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return BroadcastJob(id=row.id, body=row.body, audience=row.audience)

    async def finish_broadcast(self, broadcast_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(BroadcastRow)
            .where(BroadcastRow.id == broadcast_id)
            .values(status="done", updated_at=now)
        )
        await self._session.flush()

    async def remember_broadcast_target(self, broadcast_id: UUID, user_id: UUID) -> None:
        await _save(
            self._session,
            BroadcastTargetRow(broadcast_id=broadcast_id, user_id=user_id),
        )

    async def broadcast_user_ids(
        self,
        audience: str,
        broadcast_id: UUID,
        now: datetime,
        limit: int = BROADCAST_BATCH,
    ) -> list[UUID]:
        targeted = select(BroadcastTargetRow.user_id).where(
            BroadcastTargetRow.broadcast_id == broadcast_id
        )
        statement = select(UserRow.id).where(
            UserRow.deleted_at.is_(None),
            UserRow.is_blocked.is_(False),
            UserRow.id.not_in(targeted),
        )
        if audience == "inactive":
            last_seen = (
                select(func.max(AuthSessionRow.created_at))
                .where(AuthSessionRow.user_id == UserRow.id)
                .correlate(UserRow)
                .scalar_subquery()
            )
            statement = statement.where(
                func.coalesce(last_seen, UserRow.created_at) < now - timedelta(days=INACTIVE_DAYS)
            )
        elif audience == "topup":
            recent = select(OrderRow.user_id).where(
                OrderRow.user_id.is_not(None),
                OrderRow.kind == "topup",
                OrderRow.status == "paid",
                OrderRow.updated_at >= now - timedelta(days=TOPUP_DAYS),
            )
            statement = statement.where(UserRow.id.in_(recent))
        elif audience == "premium":
            statement = statement.where(UserRow.id.in_(_open_premium(now)))
        elif audience != "all":
            return []
        result = await self._session.execute(statement.order_by(UserRow.id).limit(limit))
        return list(result.scalars())


class SupportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        subject: str,
        message: str,
        now: datetime,
    ) -> UUID:
        row = SupportTicketRow(
            user_id=user_id,
            subject=subject,
            message=message,
            status="open",
            created_at=now,
            updated_at=now,
        )
        await _save(self._session, row)
        return row.id

    async def list_all(self, limit: int = 100) -> list[SupportTicket]:
        result = await self._session.execute(
            select(
                SupportTicketRow.id,
                SupportTicketRow.user_id,
                UserRow.telegram_id,
                UserRow.username,
                ProfileRow.display_name,
                SupportTicketRow.subject,
                SupportTicketRow.message,
                SupportTicketRow.status,
                SupportTicketRow.created_at,
                SupportTicketRow.closed_at,
            )
            .join(UserRow, UserRow.id == SupportTicketRow.user_id)
            .outerjoin(ProfileRow, ProfileRow.user_id == UserRow.id)
            .order_by(SupportTicketRow.created_at.desc())
            .limit(limit)
        )
        return [
            SupportTicket(
                id=item[0],
                user_id=item[1],
                telegram_id=int(item[2]),
                username=item[3],
                display_name=item[4],
                subject=item[5],
                message=item[6],
                status=item[7],
                created_at=item[8],
                closed_at=item[9],
            )
            for item in result.all()
        ]

    async def close(self, ticket_id: UUID, now: datetime) -> bool:
        row = await self._session.get(SupportTicketRow, ticket_id)
        if row is None or row.status == "closed":
            return False
        row.status = "closed"
        row.closed_at = now
        row.updated_at = now
        await self._session.flush()
        return True

    async def get(self, ticket_id: UUID) -> SupportTicket | None:
        result = await self._session.execute(
            select(
                SupportTicketRow.id,
                SupportTicketRow.user_id,
                UserRow.telegram_id,
                UserRow.username,
                ProfileRow.display_name,
                SupportTicketRow.subject,
                SupportTicketRow.message,
                SupportTicketRow.status,
                SupportTicketRow.created_at,
                SupportTicketRow.closed_at,
            )
            .join(UserRow, UserRow.id == SupportTicketRow.user_id)
            .outerjoin(ProfileRow, ProfileRow.user_id == UserRow.id)
            .where(SupportTicketRow.id == ticket_id)
        )
        item = result.first()
        if item is None:
            return None
        return SupportTicket(
            id=item[0],
            user_id=item[1],
            telegram_id=int(item[2]),
            username=item[3],
            display_name=item[4],
            subject=item[5],
            message=item[6],
            status=item[7],
            created_at=item[8],
            closed_at=item[9],
        )


def _open_premium(now: datetime) -> Select[UUID]:
    period_end = case(
        (
            SubscriptionRow.source == "subscription",
            func.coalesce(SubscriptionRow.grace_until, SubscriptionRow.current_period_end),
        ),
        else_=SubscriptionRow.current_period_end,
    )
    return select(SubscriptionRow.user_id).where(
        SubscriptionRow.status == "active",
        SubscriptionRow.revoked_at.is_(None),
        SubscriptionRow.source.in_(SOURCES),
        SubscriptionRow.current_period_start <= now,
        period_end > now,
    )


def _apply_profile(row: ProfileRow, draft: ProfileDraft) -> None:
    row.display_name = draft.display_name
    row.birth_date = draft.birth_date
    row.birth_time = draft.birth_time
    row.birth_time_unknown = draft.birth_time_unknown
    row.birth_place = draft.birth_place
    row.latitude = draft.latitude
    row.longitude = draft.longitude
    row.timezone = draft.timezone
    row.onboarding_step = "done"
    row.updated_at = now_utc()


def _apply_related(row: RelatedProfileRow, draft: ProfileDraft) -> None:
    row.display_name = draft.display_name
    row.birth_date = draft.birth_date
    row.birth_time = draft.birth_time
    row.birth_time_unknown = draft.birth_time_unknown
    row.birth_place = draft.birth_place
    row.latitude = draft.latitude
    row.longitude = draft.longitude
    row.timezone = draft.timezone


def _user(row: UserRow) -> User:
    return User(
        id=row.id,
        telegram_id=row.telegram_id,
        username=row.username,
        language_code=row.language_code,
        referral_code=row.referral_code,
        referred_by=row.referred_by,
        bot_welcomed=getattr(row, "bot_welcomed", False),
    )


def _place_hits(row: GeocodeCacheRow) -> list[PlaceHit]:
    raw = row.provider_payload.get("results")
    if isinstance(raw, list):
        hits: list[PlaceHit] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            latitude = item.get("latitude")
            longitude = item.get("longitude")
            if (
                not isinstance(label, str)
                or not isinstance(latitude, str)
                or not isinstance(longitude, str)
            ):
                continue
            hits.append(PlaceHit(label, Decimal(latitude), Decimal(longitude)))
        if hits:
            return hits
    return [PlaceHit(row.display_name, row.latitude, row.longitude)]


def _profile(row: ProfileRow) -> Profile:
    return Profile(
        id=row.id,
        user_id=row.user_id,
        display_name=row.display_name,
        birth_date=row.birth_date,
        birth_time=row.birth_time,
        birth_time_unknown=row.birth_time_unknown,
        birth_place=row.birth_place,
        latitude=row.latitude,
        longitude=row.longitude,
        timezone=row.timezone,
        onboarding_step=row.onboarding_step,
        streak_count=row.streak_count,
        streak_last_date=row.streak_last_date,
    )


def _charge(row: PaymentChargeRow) -> PaymentCharge:
    return PaymentCharge(
        id=row.id,
        order_id=row.order_id,
        user_id=row.user_id,
        telegram_payment_charge_id=row.telegram_payment_charge_id,
        amount_stars=row.amount_stars,
    )


def _counter(row: UsageCounterRow) -> UsageCounter:
    return UsageCounter(
        id=row.id,
        user_id=row.user_id,
        counter_key=row.counter_key,
        used=row.used,
        reserved=row.reserved,
        quota_limit=row.quota_limit,
        period_start=row.period_start,
        period_end=row.period_end,
    )


def _grant(row: SubscriptionRow) -> Grant:
    return Grant(
        id=row.id,
        user_id=row.user_id,
        source=row.source,
        status=row.status,
        period_start=row.current_period_start,
        period_end=row.current_period_end,
        grace_until=row.grace_until,
        revoked_at=row.revoked_at,
    )


def _idempotency(row: IdempotencyKeyRow) -> IdempotencyRecord:
    return IdempotencyRecord(
        id=row.id,
        user_id=row.user_id,
        key=row.idempotency_key,
        feature=row.feature,
        status=row.status,
        result=_object_dict(row.result) if row.result is not None else None,
    )


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Conflict("stored json is not an object")
    return {str(key): item for key, item in value.items()}


async def _drop_natal_cache(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        delete(ForecastCacheRow).where(
            ForecastCacheRow.user_id == user_id,
            ForecastCacheRow.kind == "natal",
        )
    )


async def _drop_natal_spend(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        delete(StarSpendRow).where(
            StarSpendRow.user_id == user_id,
            StarSpendRow.feature == "natal",
        )
    )
