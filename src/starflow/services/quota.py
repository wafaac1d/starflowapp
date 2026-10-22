"""Единственная точка допуска к лимитам.

preview только читает. reserve увеличивает резерв, commit переносит его в used
в той же транзакции, где сохранён результат, release возвращает резерв, если
результат не сохранён. Успех выдачи — строка результата в этой транзакции.
Повтор с тем же ключом отдаёт сохранённое тело и не резервирует снова.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.entitlement import access_end, question_grant
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.local_time import user_week
from starflow.domain.plans import FeatureRule, Plans
from starflow.domain.quota import (
    Allowed,
    LimitReached,
    PremiumRequired,
    QuotaDecision,
    idempotency_key_ok,
)
from starflow.domain.records import IdempotencyRecord, UsageCounter
from starflow.domain.time import now_utc
from starflow.repositories.protocols import UserRepository
from starflow.repositories.sql import (
    AssistantMessageRepository,
    FavoriteRepository,
    ForecastHistoryRepository,
    IdempotencyRepository,
    ProfileRepository,
    RelatedProfileRepository,
    SubscriptionRepository,
    UsageCounterRepository,
)

Window = tuple[datetime, datetime, int, str]


@dataclass(frozen=True)
class StoredResult:
    body: dict[str, object]
    replayed: bool


class QuotaStore(Protocol):
    users: UserRepository
    profiles: ProfileRepository
    subscriptions: SubscriptionRepository
    usage: UsageCounterRepository
    idempotency: IdempotencyRepository
    favorites: FavoriteRepository
    forecast_history: ForecastHistoryRepository
    related_profiles: RelatedProfileRepository
    assistant_messages: AssistantMessageRepository

    async def commit(self) -> None: ...


class QuotaWork(Protocol):
    async def __aenter__(self) -> QuotaStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class ResultWriter(Protocol):
    def __call__(self, store: QuotaStore) -> Awaitable[dict[str, object]]: ...


def meter_key(feature: str, grant_id: UUID | None = None) -> str:
    if grant_id is None:
        return feature
    return f"{feature}:{grant_id}"


class QuotaService:
    def __init__(
        self,
        uow_factory: Callable[[], QuotaWork],
        plans: Plans,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._plans = plans
        self._clock = clock or now_utc

    async def preview(self, user_id: UUID, feature: str) -> QuotaDecision:
        rule = self._plans.rule(feature)
        async with self._uow_factory() as uow:
            closed = await _entitled(uow, user_id, rule, self._clock())
            if closed is not None:
                return closed
            if rule.gate in {"open", "premium"}:
                return Allowed()
            if rule.gate == "capacity":
                occupied = await _occupied(uow, user_id, rule)
                if occupied:
                    return LimitReached(None)
                return Allowed()
            window = await _window(uow, user_id, rule, self._clock())
            if not isinstance(window, tuple):
                return window
            start, end, limit, counter_key = window
            counter = await uow.usage.find(user_id, counter_key, start)
            used = 0 if counter is None else counter.used + counter.reserved
            if used >= limit:
                return LimitReached(end)
            return Allowed()

    async def execute(
        self,
        user_id: UUID,
        feature: str,
        key: str,
        producer: ResultWriter,
    ) -> StoredResult | QuotaDecision:
        if not idempotency_key_ok(key):
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        reserved = await self._reserve(user_id, feature, key)
        if isinstance(reserved, StoredResult) or not isinstance(reserved, Allowed):
            return reserved
        try:
            return await self._commit(user_id, feature, key, producer, charge=True)
        except Exception:
            await self._release(user_id, key)
            raise

    async def hold(self, user_id: UUID, feature: str, key: str) -> StoredResult | QuotaDecision:
        if not idempotency_key_ok(key):
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        return await self._reserve(user_id, feature, key)

    async def finish(
        self,
        user_id: UUID,
        feature: str,
        key: str,
        producer: ResultWriter,
        *,
        charge: bool,
    ) -> StoredResult:
        return await self._commit(user_id, feature, key, producer, charge=charge)

    async def release_hold(self, user_id: UUID, key: str) -> None:
        await self._release(user_id, key)

    async def remaining(self, user_id: UUID, feature: str) -> int | None:
        rule = self._plans.rule(feature)
        async with self._uow_factory() as uow:
            window = await _window(uow, user_id, rule, self._clock())
            if not isinstance(window, tuple):
                return None
            start, _end, limit, counter_key = window
            counter = await uow.usage.find(user_id, counter_key, start)
            used = 0 if counter is None else counter.used + counter.reserved
            return max(0, limit - used)

    async def _reserve(
        self,
        user_id: UUID,
        feature: str,
        key: str,
    ) -> StoredResult | QuotaDecision:
        last = Conflict("unique constraint rejected the write")
        for _attempt in range(3):
            try:
                return await self._reserve_once(user_id, feature, key)
            except Conflict as error:
                if error.args and error.args[0] == "unique constraint rejected the write":
                    last = error
                    continue
                raise
        raise last

    async def _reserve_once(
        self,
        user_id: UUID,
        feature: str,
        key: str,
    ) -> StoredResult | QuotaDecision:
        rule = self._plans.rule(feature)
        async with self._uow_factory() as uow:
            await uow.users.lock(user_id)
            existing = await uow.idempotency.lock(user_id, key)
            if existing is not None and existing.feature != feature:
                raise Conflict("idempotency key belongs to another action")
            stored = _replay(existing)
            if stored is not None:
                return stored
            if existing is not None and existing.status == "reserved":
                return Allowed()
            closed = await _entitled(uow, user_id, rule, self._clock())
            if closed is not None:
                return closed
            marker: dict[str, object] = {}
            if rule.gate == "metered":
                metered = await _meter(uow, user_id, rule, self._clock())
                if not isinstance(metered, UsageCounter):
                    return metered
                await uow.usage.change(metered.id, used_delta=0, reserved_delta=1)
                marker = {"counter_id": str(metered.id)}
            elif rule.gate == "capacity" and await _occupied(uow, user_id, rule):
                return LimitReached(None)
            await uow.idempotency.hold(user_id, key, feature, marker, existing)
            await uow.commit()
            return Allowed()

    async def _commit(
        self,
        user_id: UUID,
        feature: str,
        key: str,
        producer: ResultWriter,
        *,
        charge: bool,
    ) -> StoredResult:
        rule = self._plans.rule(feature)
        async with self._uow_factory() as uow:
            await uow.users.lock(user_id)
            current = await uow.idempotency.lock(user_id, key)
            stored = _replay(current)
            if stored is not None:
                return stored
            if current is None or current.status != "reserved":
                raise Conflict("idempotency reservation is missing")
            body = await producer(uow)
            if rule.gate == "metered":
                counter_id = _counter_id(current.result)
                if counter_id is None:
                    raise Conflict("usage counter is missing")
                used_delta = 1 if charge else 0
                await uow.usage.change(counter_id, used_delta=used_delta, reserved_delta=-1)
            await uow.idempotency.complete(current.id, body)
            await uow.commit()
            return StoredResult(body, False)

    async def _release(self, user_id: UUID, key: str) -> None:
        async with self._uow_factory() as uow:
            await uow.users.lock(user_id)
            current = await uow.idempotency.lock(user_id, key)
            if current is None or current.status != "reserved":
                return
            counter_id = _counter_id(current.result)
            if counter_id is not None:
                counter = await uow.usage.get(counter_id)
                if counter is not None and counter.reserved > 0:
                    await uow.usage.change(counter_id, used_delta=0, reserved_delta=-1)
            await uow.idempotency.mark_released(current.id)
            await uow.commit()


def _replay(record: IdempotencyRecord | None) -> StoredResult | None:
    if record is None or record.status != "committed" or record.result is None:
        return None
    return StoredResult(record.result, True)


def _counter_id(result: dict[str, object] | None) -> UUID | None:
    if result is None:
        return None
    raw = result.get("counter_id")
    if not isinstance(raw, str):
        return None
    return UUID(raw)


async def _entitled(
    uow: QuotaStore,
    user_id: UUID,
    rule: FeatureRule,
    now: datetime,
) -> PremiumRequired | None:
    if not rule.requires_entitlement and rule.gate != "premium":
        return None
    grants = await uow.subscriptions.list_for_user(user_id)
    if access_end(grants, now) is None:
        return PremiumRequired()
    return None


async def _window(
    uow: QuotaStore,
    user_id: UUID,
    rule: FeatureRule,
    now: datetime,
) -> Window | QuotaDecision:
    if rule.limit is None or rule.window is None:
        raise Conflict("metered feature has no limit")
    if rule.window == "user_week":
        profile = await uow.profiles.get_by_user_id(user_id)
        if profile is None or profile.timezone is None:
            raise FieldInvalid("timezone", "errors.timezone_invalid")
        start, end = user_week(now, profile.timezone)
        return start, end, rule.limit, meter_key(rule.code)
    grants = await uow.subscriptions.list_for_user(user_id)
    grant = question_grant(grants, now)
    if grant is None:
        return PremiumRequired()
    if now >= grant.period_end:
        return LimitReached(grant.period_end)
    return grant.period_start, grant.period_end, rule.limit, meter_key(rule.code, grant.id)


async def _meter(
    uow: QuotaStore,
    user_id: UUID,
    rule: FeatureRule,
    now: datetime,
) -> UsageCounter | QuotaDecision:
    window = await _window(uow, user_id, rule, now)
    if not isinstance(window, tuple):
        return window
    start, end, limit, counter_key = window
    counter = await uow.usage.lock_window(user_id, counter_key, start)
    if counter is None:
        counter = await uow.usage.open_counter(user_id, counter_key, start, end, limit)
    if counter.used + counter.reserved >= counter.quota_limit:
        return LimitReached(counter.period_end)
    return counter


async def _occupied(uow: QuotaStore, user_id: UUID, rule: FeatureRule) -> bool:
    if rule.limit is None:
        return True
    if rule.code == "favorite":
        count = await uow.favorites.count_for_user(user_id)
    elif rule.code == "related_profile":
        count = await uow.related_profiles.count_for_owner(user_id)
    else:
        raise Conflict("capacity feature is unknown")
    holds = await uow.idempotency.count_reserved(user_id, rule.code)
    return count + holds >= rule.limit
