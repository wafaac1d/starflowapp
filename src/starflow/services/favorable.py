"""Благоприятные дни месяца. Модель зовётся один раз на человека, событие и сутки."""

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from types import TracebackType
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from starflow.ai.catalog import PromptCatalog
from starflow.ai.client import CircuitOpen, ModelReply
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.calendar_reading import parse_month
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.favorable import (
    FavorableDay,
    accept_favorable,
    event_label,
    favorable_subject,
    nearest_favorable,
)
from starflow.domain.segments import facts_text
from starflow.domain.stars import FAVORABLE_STARS
from starflow.domain.time import now_utc
from starflow.logging import get_logger
from starflow.repositories.sql import (
    AiRequestRepository,
    ForecastHistoryRepository,
    ProfileRepository,
    SubscriptionRepository,
)

_LOG = get_logger("favorable")
_REPAIR = (
    "Прошлый json не подошёл. Верни days: от 4 до 8 дат этого месяца. "
    "У каждой date, start, end и note без emoji. start раньше end."
)


class FavorableModel(Protocol):
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


class FavorableStars(Protocol):
    async def owns(self, user_id: UUID, feature: str, subject: str) -> bool: ...


class FavorableStore(Protocol):
    profiles: ProfileRepository
    ai_requests: AiRequestRepository
    subscriptions: SubscriptionRepository
    forecast_history: ForecastHistoryRepository

    async def commit(self) -> None: ...


class FavorableWork(Protocol):
    async def __aenter__(self) -> FavorableStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class FavorableStatus:
    chosen_event: str | None
    chosen_custom: str | None
    chosen_label: str | None
    is_premium: bool


@dataclass(frozen=True)
class FavorableMonth:
    status: str
    event: str
    label: str
    month: str
    timezone: str
    access: str
    price: int
    days: tuple[FavorableDay, ...]
    free_chosen_label: str | None = None


class FavorableService:
    def __init__(
        self,
        uow_factory: Callable[[], FavorableWork],
        cache: TwoLevelCache,
        model: FavorableModel,
        prompts: PromptCatalog,
        *,
        model_name: str,
        zone_name: str,
        stars: FavorableStars | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._cache = cache
        self._model = model
        self._prompts = prompts
        self._model_name = model_name
        self._zone_name = zone_name
        self._stars = stars
        self._clock = clock or now_utc

    async def status(self, user_id: UUID) -> FavorableStatus:
        now = self._clock()
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, now)
            zone = profile.timezone or self._zone_name
            today = now.astimezone(ZoneInfo(zone)).date()
            found = await uow.forecast_history.find(user_id, "favorable", today)
        if found is None:
            return FavorableStatus(
                chosen_event=None,
                chosen_custom=None,
                chosen_label=None,
                is_premium=premium,
            )
        _id, payload = found
        event = cast(str | None, payload.get("event"))
        custom = cast(str | None, payload.get("custom"))
        label = cast(str | None, payload.get("label"))
        return FavorableStatus(
            chosen_event=event,
            chosen_custom=custom,
            chosen_label=label,
            is_premium=premium,
        )

    async def month(
        self,
        user_id: UUID,
        month: str,
        event: str,
        custom: str,
    ) -> FavorableMonth:
        try:
            year, month_number = parse_month(month)
        except ValueError as error:
            raise FieldInvalid("month", "errors.validation") from error
        label = event_label(event, custom)
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, self._clock())
        zone = profile.timezone or self._zone_name
        today = self._clock().astimezone(ZoneInfo(zone)).date()
        today_iso = today.isoformat()

        owned = False
        is_free = not premium
        if is_free and self._stars is not None:
            subject = favorable_subject(month, event, custom)
            owned = await self._stars.owns(user_id, "favorable", subject)
            if owned:
                is_free = False

        if is_free:
            async with self._uow_factory() as uow:
                found_hist = await uow.forecast_history.find(user_id, "favorable", today)
            if found_hist is not None:
                _id, recorded = found_hist
                rec_event = recorded.get("event")
                rec_custom = recorded.get("custom", "")
                rec_label = cast(str, recorded.get("label", ""))
                matches = event == rec_event and (event != "custom" or custom == rec_custom)
                if not matches:
                    return FavorableMonth(
                        status="ready",
                        event=event,
                        label=label,
                        month=month,
                        timezone=zone,
                        access="locked",
                        price=FAVORABLE_STARS,
                        days=(),
                        free_chosen_label=rec_label,
                    )

        born = "unknown" if profile.birth_date is None else profile.birth_date.strftime("%d.%m.%Y")
        clock = (
            "unknown"
            if profile.birth_time_unknown or profile.birth_time is None
            else profile.birth_time.strftime("%H:%M")
        )
        sun = "unknown" if profile.birth_date is None else calendar_sign(profile.birth_date)
        facts = facts_text({"sun": sun, "birth_date": born, "birth_time": clock, "timezone": zone})
        prompt = self._prompts.get("favorable")
        key = "|".join(
            (
                "favorable",
                str(user_id),
                event,
                label.casefold(),
                month,
                str(prompt.version),
                born,
                clock,
                zone,
            )
        )

        async def produce() -> dict[str, object]:
            return await self._ask(user_id, year, month_number, label, month, facts, zone)

        hit = await self._cache.get_or_create(
            key, "favorable", _midnight(self._clock(), zone), produce
        )
        view = _month(hit.payload, event, label, month, zone)

        if is_free and view.status == "ready":
            async with self._uow_factory() as uow:
                existing = await uow.forecast_history.find(user_id, "favorable", today)
                if existing is None:
                    try:
                        await uow.forecast_history.add(
                            user_id,
                            "favorable",
                            today,
                            {"event": event, "custom": custom, "label": label},
                        )
                        await uow.commit()
                    except Conflict:
                        pass

        return self._access(view, today_iso, premium, owned)

    def _access(
        self,
        view: FavorableMonth,
        today_iso: str,
        premium: bool,
        owned: bool,
    ) -> FavorableMonth:
        if view.status != "ready" or len(view.days) <= 1:
            opened = view.status == "ready" and bool(view.days)
            return replace(view, access="full" if opened else "preview", price=0)
        if premium or owned:
            return replace(view, access="full", price=0)
        return replace(
            view,
            access="preview",
            price=FAVORABLE_STARS,
            days=nearest_favorable(view.days, today_iso),
        )

    async def _ask(
        self,
        user_id: UUID,
        year: int,
        month_number: int,
        label: str,
        month: str,
        facts: str,
        zone: str,
    ) -> dict[str, object]:
        prompt = self._prompts.get("favorable")
        user = (
            prompt.user.replace("{facts}", facts)
            .replace("{event}", label)
            .replace("{month}", month)
        )
        repair = f"{user}\n{_REPAIR}"
        for text in (user, repair):
            parsed = await self._complete(
                user_id, prompt.system, text, prompt.temperature, prompt.max_tokens
            )
            accepted = None if parsed is None else accept_favorable(year, month_number, parsed)
            if accepted is not None:
                return _ready(accepted, zone)
        _LOG.warning("favorable_uses_fallback", model=self._model_name)
        return {"status": "unavailable", "source": "fallback", "timezone": zone}

    async def _complete(
        self,
        user_id: UUID,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> object | None:
        try:
            reply = await self._model.complete_forecast(
                model=self._model_name,
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
        except CircuitOpen:
            await self._log(user_id, "circuit_open", None, "circuit_open")
            return None
        except Exception as exc:
            await self._log(user_id, "error", None, type(exc).__name__)
            return None
        await self._log(user_id, "ok", reply, None)
        try:
            return cast(object, json.loads(reply.content))
        except json.JSONDecodeError:
            _LOG.warning("model_reply_rejected", kind="favorable", model=self._model_name)
            return None

    async def _log(
        self,
        user_id: UUID,
        status: str,
        reply: ModelReply | None,
        error_code: str | None,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.ai_requests.add(
                user_id,
                self._model_name,
                "favorable",
                status,
                None if reply is None else reply.prompt_tokens,
                None if reply is None else reply.completion_tokens,
                None if reply is None else reply.latency_ms,
                error_code,
            )
            await uow.commit()


def _ready(days: tuple[FavorableDay, ...], zone: str) -> dict[str, object]:
    payload: dict[str, object] = {"status": "ready", "source": "model", "timezone": zone}
    payload["days"] = [
        {"date": day.date, "start": day.start, "end": day.end, "note": day.note} for day in days
    ]
    return payload


def _month(
    payload: dict[str, object],
    event: str,
    label: str,
    month: str,
    zone: str,
) -> FavorableMonth:
    raw = payload.get("days")
    days: list[FavorableDay] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            date = item.get("date")
            start = item.get("start")
            end = item.get("end")
            note = item.get("note")
            if (
                isinstance(date, str)
                and isinstance(start, str)
                and isinstance(end, str)
                and isinstance(note, str)
            ):
                days.append(FavorableDay(date, start, end, note))
    status = payload.get("status")
    return FavorableMonth(
        status=status if isinstance(status, str) else "unavailable",
        event=event,
        label=label,
        month=month,
        timezone=zone,
        access="preview",
        price=0,
        days=tuple(days),
    )


def _midnight(moment: datetime, zone_name: str) -> datetime:
    zone = ZoneInfo(zone_name)
    local = moment.astimezone(zone)
    return datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=zone)
