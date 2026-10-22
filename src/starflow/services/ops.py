"""Планирование уведомлений, прогрев кэша и очистка. Модель для рассылки не вызывается."""

import asyncio
import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from starflow.ai.catalog import PromptCatalog
from starflow.ai.client import ModelReply
from starflow.ai.guard import guarded_copy
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.notify_clock import (
    is_due,
    known_zone,
    local_date,
    parse_slot,
    slot_label,
    warm_window,
)
from starflow.domain.records import AdminSnapshot
from starflow.domain.segments import (
    expires_at,
    facts_text,
    forecast_cache_key,
    moon_segment,
    pair_segment,
    period_key,
    representative_facts,
)
from starflow.domain.stations import Station, find_stations
from starflow.domain.time import now_utc
from starflow.domain.warmup_plan import SIGNS, WARM_BUDGET, WARM_PARALLEL, unordered_pairs
from starflow.repositories.protocols import OutboxRepository, UserRepository
from starflow.repositories.sql import (
    ForecastCacheRepository,
    NotificationSettingsRepository,
    OpsRepository,
    ProfileRepository,
    SubscriptionRepository,
)


class OpsStore(Protocol):
    users: UserRepository
    profiles: ProfileRepository
    notification_settings: NotificationSettingsRepository
    subscriptions: SubscriptionRepository
    forecast_cache: ForecastCacheRepository
    outbox: OutboxRepository
    ops: OpsRepository

    async def commit(self) -> None: ...


class OpsWork(Protocol):
    async def __aenter__(self) -> OpsStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class TextModel(Protocol):
    async def complete_forecast(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelReply: ...


class BodySpeed(Protocol):
    def positions(self, moment: datetime) -> tuple[object, ...]: ...


class BudgetSpent(Exception):
    """Лимит прогрева на этот запуск уже выбран."""


class OpsService:
    def __init__(
        self,
        uow_factory: Callable[[], OpsWork],
        prompts: PromptCatalog,
        cache: TwoLevelCache,
        model: TextModel,
        ephemeris: BodySpeed,
        *,
        zone_name: str,
        locale: str,
        fast_model: str,
        pro_model: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._prompts = prompts
        self._cache = cache
        self._model = model
        self._ephemeris = ephemeris
        self._zone_name = zone_name
        self._locale = locale
        self._fast_model = fast_model
        self._pro_model = pro_model
        self._clock = clock or now_utc

    async def plan(self) -> int:
        now = self._clock()
        stations = self.stations(now - timedelta(days=2), now + timedelta(days=40))
        async with self._uow_factory() as uow:
            premium = await uow.subscriptions.premium_user_ids(now)
            created = 0
            for row in await uow.notification_settings.enabled():
                if not is_due(now, row.timezone, row.digest_local_time):
                    continue
                day = local_date(now, row.timezone).date()
                birth = await _birth(uow, row.user_id)
                if row.day_enabled:
                    created += await self._notice(
                        uow,
                        row.user_id,
                        "day",
                        day,
                        now,
                        "reading/day",
                        await self._day_ready(uow, birth, now),
                    )
                if row.moon_enabled:
                    created += await self._notice(
                        uow,
                        row.user_id,
                        "moon",
                        day,
                        now,
                        "reading/moon",
                        await self._moon_ready(uow, now),
                    )
                if row.retro_enabled and row.user_id in premium:
                    created += await self._retro(uow, row.user_id, day, now, stations)
            await uow.commit()
        return created

    async def warm(self) -> int:
        now = self._clock()
        if not warm_window(now, self._zone_name):
            return 0
        total = await self.warm_signs(now)
        local = now.astimezone(ZoneInfo(self._zone_name))
        if local.weekday() == 0:
            total += await self.warm_pairs(now)
        return total

    async def warm_signs(self, moment: datetime) -> int:
        version = self._prompts.get("day").version
        keys = [
            (
                forecast_cache_key(
                    "day",
                    period_key("day", moment, self._zone_name),
                    sign,
                    "",
                    self._locale,
                    version,
                ),
                "day",
                sign,
            )
            for sign in SIGNS
        ]
        moon = period_key("moon", moment, self._zone_name)
        keys.append(
            (
                forecast_cache_key(
                    "moon",
                    moon,
                    moon_segment(local_date(moment, self._zone_name).date()),
                    "",
                    self._locale,
                    self._prompts.get("moon").version,
                ),
                "moon",
                moon,
            )
        )
        return await self._fill(moment, keys)

    async def warm_pairs(self, moment: datetime) -> int:
        version = self._prompts.get("compatibility").version
        period = period_key("compatibility", moment, self._zone_name)
        keys = [
            (
                forecast_cache_key(
                    "compatibility",
                    period,
                    pair_segment(left, right),
                    "",
                    self._locale,
                    version,
                ),
                "compatibility",
                pair_segment(left, right),
            )
            for left, right in unordered_pairs()
        ]
        return await self._fill(moment, keys)

    async def purge(self) -> None:
        async with self._uow_factory() as uow:
            await uow.ops.purge(self._clock())
            await uow.commit()

    async def preferences(self, user_id: UUID) -> tuple[str, str, bool, bool, bool]:
        async with self._uow_factory() as uow:
            row = await uow.notification_settings.read(user_id)
            profile = await uow.profiles.get_by_user_id(user_id)
        if row is None:
            zone = self._zone_name
            if profile is not None and profile.timezone:
                zone = profile.timezone
            return "09:00", zone, False, False, False
        return (
            slot_label(row.digest_local_time),
            row.timezone,
            row.day_enabled,
            row.moon_enabled,
            row.retro_enabled,
        )

    async def save_preferences(
        self,
        user_id: UUID,
        local_time: str,
        timezone: str,
        *,
        day: bool,
        moon: bool,
        retro: bool,
    ) -> tuple[str, str, bool, bool, bool]:
        try:
            slot = parse_slot(local_time)
            known_zone(timezone)
        except ValueError as error:
            field = "timezone" if str(error) == "zone" else "local_time"
            key = "errors.timezone_invalid" if field == "timezone" else "errors.time_invalid"
            raise FieldInvalid(field, key) from error
        async with self._uow_factory() as uow:
            await uow.notification_settings.save_preferences(
                user_id,
                slot,
                timezone,
                day=day,
                moon=moon,
                retro=retro,
            )
            await uow.commit()
        return local_time, timezone, day, moon, retro

    async def snapshot(self, start: datetime, end: datetime) -> AdminSnapshot:
        async with self._uow_factory() as uow:
            return await uow.ops.snapshot(start, end)

    def stations(self, start: datetime, end: datetime) -> tuple[Station, ...]:
        def speed_at(moment: datetime, planet: str) -> float:
            for body in self._ephemeris.positions(moment):
                name = getattr(body, "name", None)
                speed = getattr(body, "speed", None)
                if name == planet and isinstance(speed, int | float):
                    return float(speed)
            return 0.0

        return find_stations(speed_at, start, end)

    async def _day_ready(self, uow: OpsStore, birth: date | None, moment: datetime) -> bool:
        if birth is None:
            return False
        sign = calendar_sign(birth)
        key = forecast_cache_key(
            "day",
            period_key("day", moment, self._zone_name),
            sign,
            "",
            self._locale,
            self._prompts.get("day").version,
        )
        return await uow.forecast_cache.peek(key, moment)

    async def _moon_ready(self, uow: OpsStore, moment: datetime) -> bool:
        day = local_date(moment, self._zone_name).date()
        key = forecast_cache_key(
            "moon",
            period_key("moon", moment, self._zone_name),
            moon_segment(day),
            "",
            self._locale,
            self._prompts.get("moon").version,
        )
        return await uow.forecast_cache.peek(key, moment)

    async def _notice(
        self,
        uow: OpsStore,
        user_id: UUID,
        kind: str,
        day: date,
        moment: datetime,
        page: str,
        ready: bool,
    ) -> int:
        text_key = f"bot.{kind}_ready" if ready else f"bot.{kind}_fallback"
        try:
            await uow.outbox.enqueue(
                user_id,
                kind,
                text_key,
                day,
                moment,
                event_key=day.isoformat(),
                page=page,
            )
        except Conflict:
            return 0
        return 1

    async def _retro(
        self,
        uow: OpsStore,
        user_id: UUID,
        day: date,
        moment: datetime,
        stations: tuple[Station, ...],
    ) -> int:
        zone = ZoneInfo(self._zone_name)
        created = 0
        for station in stations:
            station_day = station.start.astimezone(zone).date()
            if day == station_day - timedelta(days=3):
                phase = "preview"
            elif day == station_day:
                phase = "start"
            else:
                continue
            try:
                await uow.outbox.enqueue(
                    user_id,
                    "retro",
                    f"bot.retro_{phase}",
                    day,
                    moment,
                    event_key=f"{station.planet}:{station_day.isoformat()}:{phase}",
                    page="retro",
                    planet=station.planet,
                )
            except Conflict:
                continue
            created += 1
        return created

    async def _fill(
        self,
        moment: datetime,
        keys: list[tuple[str, str, str]],
    ) -> int:
        spent = 0
        lock = asyncio.Lock()
        made = 0
        gate = asyncio.Semaphore(WARM_PARALLEL)

        async def produce(kind: str, segment: str) -> dict[str, object]:
            nonlocal spent
            async with lock:
                if spent >= WARM_BUDGET:
                    raise BudgetSpent
                spent += 1
            return await self._generate(kind, segment)

        async def one(key: str, kind: str, segment: str) -> None:
            nonlocal made

            async def produce_one(
                kind: str = kind,
                segment: str = segment,
            ) -> dict[str, object]:
                return await produce(kind, segment)

            async with gate:
                try:
                    hit = await self._cache.get_or_create(
                        key,
                        kind,
                        expires_at(kind, moment, self._zone_name),
                        produce_one,
                    )
                except (BudgetSpent, Exception):
                    return
                if hit.generated:
                    made += 1

        await asyncio.gather(*(one(key, kind, segment) for key, kind, segment in keys))
        return made

    async def _generate(self, kind: str, segment: str) -> dict[str, object]:
        prompt = self._prompts.get(kind)
        facts = representative_facts(kind, segment)
        user = prompt.user.replace("{facts}", facts_text(facts))
        last = "invalid"
        for _attempt in range(2):
            model_name = self._fast_model if prompt.tier == "fast" else self._pro_model
            reply = await self._model.complete_forecast(
                model=model_name,
                system=prompt.system,
                user=user,
                temperature=float(prompt.temperature),
                max_tokens=int(prompt.max_tokens),
                json_mode=True,
            )
            parsed = _payload(reply.content)
            if parsed is not None:
                return parsed
            last = "invalid"
        raise ValueError(last)


async def _birth(uow: OpsStore, user_id: UUID) -> date | None:
    profile = await uow.profiles.get_by_user_id(user_id)
    if profile is None:
        return None
    return profile.birth_date


def _payload(content: str) -> dict[str, object] | None:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    title = raw.get("title")
    body = raw.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        return None
    copied = guarded_copy(title, body)
    if copied is None:
        return None
    clean_title, clean_body = copied
    return {"title": clean_title, "body": clean_body, "source": "model"}
