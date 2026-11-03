"""Сервис аффирмаций на день. Бесплатно доступен один расчёт в день по одной из категорий."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from types import TracebackType
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from structlog import get_logger

from starflow.ai.catalog import PromptCatalog
from starflow.ai.client import ModelReply
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.affirmations import (
    DEFAULT_AFFIRMATIONS,
    AffirmationCard,
    category_label,
)
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.segments import facts_text
from starflow.domain.stars import AFFIRMATION_STARS, affirmation_subject
from starflow.domain.time import now_utc
from starflow.i18n.guard import contains_emoji
from starflow.repositories.sql import (
    AffirmationKeepRepository,
    AiRequestRepository,
    ForecastHistoryRepository,
    ProfileRepository,
    SubscriptionRepository,
)

_LOG = get_logger("affirmations")
_REPAIR = "Верни только один валидный json-объект без markdown-разметки."
_CARD_OK = set("abcdefghijklmnopqrstuvwxyz0123456789:_-")


class AffirmationsModel(Protocol):
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


class AffirmationsStars(Protocol):
    async def owns(self, user_id: UUID, feature: str, subject: str) -> bool: ...


class AffirmationsStore(Protocol):
    profiles: ProfileRepository
    ai_requests: AiRequestRepository
    subscriptions: SubscriptionRepository
    forecast_history: ForecastHistoryRepository
    affirmation_keeps: AffirmationKeepRepository

    async def commit(self) -> None: ...


class AffirmationsWork(Protocol):
    async def __aenter__(self) -> AffirmationsStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class AffirmationsStatus:
    chosen_category: str | None
    chosen_label: str | None
    is_premium: bool


@dataclass(frozen=True)
class AffirmationKeepView:
    id: UUID
    card_id: str
    text: str
    category: str


@dataclass(frozen=True)
class AffirmationsView:
    category: str
    label: str
    access: str
    price: int
    cards: tuple[AffirmationCard, ...]
    free_chosen_label: str | None = None


class AffirmationsService:
    def __init__(
        self,
        uow_factory: Callable[[], AffirmationsWork],
        cache: TwoLevelCache,
        model: AffirmationsModel,
        prompts: PromptCatalog,
        *,
        model_name: str,
        zone_name: str,
        stars: AffirmationsStars | None = None,
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

    async def status(self, user_id: UUID) -> AffirmationsStatus:
        now = self._clock()
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, now)
            zone = profile.timezone or self._zone_name
            today = now.astimezone(ZoneInfo(zone)).date()
            found = await uow.forecast_history.find(user_id, "affirmation", today)
        if found is None:
            return AffirmationsStatus(
                chosen_category=None,
                chosen_label=None,
                is_premium=premium,
            )
        _id, payload = found
        cat = cast(str | None, payload.get("category"))
        label = cast(str | None, payload.get("label"))
        return AffirmationsStatus(
            chosen_category=cat,
            chosen_label=label,
            is_premium=premium,
        )

    async def get_affirmations(
        self,
        user_id: UUID,
        category: str,
    ) -> AffirmationsView:
        label = category_label(category)
        now = self._clock()
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, now)

        zone = profile.timezone or self._zone_name
        today = now.astimezone(ZoneInfo(zone)).date()
        owned = False
        if not premium and self._stars is not None:
            owned = await self._stars.owns(user_id, "affirmation", affirmation_subject(category))
        if not premium and not owned:
            blocked = await self._other_choice(user_id, category, today, label)
            if blocked is not None:
                return blocked
        cards = await self._load_cards(user_id, category, profile, zone, today)
        if premium or owned:
            return AffirmationsView(
                category=category,
                label=label,
                access="full",
                price=0,
                cards=cards,
            )
        await self._remember_free(user_id, category, label, today)
        blocked = await self._other_choice(user_id, category, today, label)
        if blocked is not None:
            return blocked
        return AffirmationsView(
            category=category,
            label=label,
            access="preview",
            price=AFFIRMATION_STARS,
            cards=cards[:1],
        )

    async def list_keeps(self, user_id: UUID) -> tuple[AffirmationKeepView, ...]:
        async with self._uow_factory() as uow:
            rows = await uow.affirmation_keeps.list_for_user(user_id)
        return tuple(
            AffirmationKeepView(
                id=row.id, card_id=row.card_id, text=row.text, category=row.category
            )
            for row in rows
        )

    async def keep(
        self,
        user_id: UUID,
        card_id: str,
        category: str,
        text: str,
    ) -> AffirmationKeepView:
        cleaned_id = card_id.strip()
        cleaned_text = " ".join(text.split())
        if (
            not cleaned_id
            or len(cleaned_id) > 80
            or any(character not in _CARD_OK for character in cleaned_id)
        ):
            raise FieldInvalid("card_id", "errors.validation")
        category_label(category)
        if not cleaned_text or len(cleaned_text) > 500 or contains_emoji(cleaned_text):
            raise FieldInvalid("text", "errors.validation")
        async with self._uow_factory() as uow:
            row = await uow.affirmation_keeps.add(user_id, cleaned_id, category, cleaned_text)
            await uow.commit()
        return AffirmationKeepView(
            id=row.id,
            card_id=row.card_id,
            text=row.text,
            category=row.category,
        )

    async def forget(self, user_id: UUID, card_id: str) -> bool:
        async with self._uow_factory() as uow:
            removed = await uow.affirmation_keeps.delete_card(user_id, card_id)
            if removed:
                await uow.commit()
        return removed

    async def _other_choice(
        self,
        user_id: UUID,
        category: str,
        today: date,
        label: str,
    ) -> AffirmationsView | None:
        del label
        async with self._uow_factory() as uow:
            found = await uow.forecast_history.find(user_id, "affirmation", today)
        if found is None:
            return None
        _id, recorded = found
        if recorded.get("category") == category:
            return None
        rec_label = recorded.get("label")
        return AffirmationsView(
            category=category,
            label=category_label(category),
            access="locked",
            price=AFFIRMATION_STARS,
            cards=(),
            free_chosen_label=rec_label if isinstance(rec_label, str) else None,
        )

    async def _remember_free(
        self,
        user_id: UUID,
        category: str,
        label: str,
        today: date,
    ) -> None:
        async with self._uow_factory() as uow:
            found = await uow.forecast_history.find(user_id, "affirmation", today)
            if found is not None:
                return
            try:
                await uow.forecast_history.add(
                    user_id,
                    "affirmation",
                    today,
                    {"category": category, "label": label},
                )
                await uow.commit()
            except Conflict:
                return

    async def _load_cards(
        self,
        user_id: UUID,
        category: str,
        profile: object,
        zone: str,
        today: date,
    ) -> tuple[AffirmationCard, ...]:
        prompt = self._prompts.get("affirmation")
        born = _born(profile)
        clock = _clock(profile)
        place = _place(profile)
        key = "|".join(
            (
                "affirmation",
                str(user_id),
                category,
                str(today),
                str(prompt.version),
                born,
                clock,
                place,
            )
        )
        expires = _next_midnight(self._clock(), zone)

        async def produce() -> dict[str, object]:
            return {"texts": list(await self._ask(user_id, category, profile, zone))}

        hit = await self._cache.get_or_create(key, "affirmation", expires, produce)
        raw = hit.payload.get("texts")
        texts = (
            tuple(item for item in raw if isinstance(item, str)) if isinstance(raw, list) else ()
        )
        return _cards(category, texts)

    async def _ask(
        self,
        user_id: UUID,
        category: str,
        profile: object,
        zone: str,
    ) -> tuple[str, ...]:
        prompt = self._prompts.get("affirmation")
        facts = facts_text(
            {
                "sun": _sun(profile),
                "birth_date": _born(profile),
                "birth_time": _clock(profile),
                "birth_place": _place(profile),
                "timezone": zone,
            }
        )
        user = (
            prompt.user.replace("{facts}", facts)
            .replace("{category}", category_label(category))
            .replace("{today}", str(self._clock().astimezone(ZoneInfo(zone)).date()))
        )
        for text in (user, f"{user}\n{_REPAIR}"):
            parsed = await self._complete(
                user_id, prompt.system, text, prompt.temperature, prompt.max_tokens
            )
            accepted = _texts(parsed)
            if accepted:
                return accepted
        _LOG.warning("affirmation_uses_fallback", model=self._model_name, category=category)
        return tuple(card.text for card in DEFAULT_AFFIRMATIONS.get(category, ()))

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
        except Exception as error:
            _LOG.warning(
                "model_call_failed",
                kind="affirmation",
                model=self._model_name,
                error_type=type(error).__name__,
            )
            await self._note(user_id, "error")
            return None
        await self._note(user_id, "ok", reply)
        try:
            return cast(object, json.loads(reply.content))
        except json.JSONDecodeError:
            _LOG.warning("model_reply_rejected", kind="affirmation", model=self._model_name)
            return None

    async def _note(self, user_id: UUID, status: str, reply: ModelReply | None = None) -> None:
        prompt_tokens = None if reply is None else reply.prompt_tokens
        completion_tokens = None if reply is None else reply.completion_tokens
        async with self._uow_factory() as uow:
            await uow.ai_requests.add(
                user_id,
                self._model_name,
                "affirmation",
                status,
                prompt_tokens,
                completion_tokens,
            )
            await uow.commit()


def _cards(category: str, texts: tuple[str, ...]) -> tuple[AffirmationCard, ...]:
    defaults = DEFAULT_AFFIRMATIONS.get(category, ())
    chosen: list[str] = []
    for item in texts:
        cleaned = item.strip()
        if cleaned and cleaned not in chosen and not contains_emoji(cleaned):
            chosen.append(cleaned)
        if len(chosen) == 3:
            break
    for card in defaults:
        if len(chosen) == 3:
            break
        if card.text not in chosen:
            chosen.append(card.text)
    backgrounds = tuple(card.bg_image for card in defaults) or ("",)
    return tuple(
        AffirmationCard(
            id=f"{category}:{index}",
            text=text,
            category=category,
            bg_image=backgrounds[index % len(backgrounds)],
        )
        for index, text in enumerate(chosen)
    )


def _texts(parsed: object | None) -> tuple[str, ...]:
    if not isinstance(parsed, dict):
        return ()
    found: list[str] = []
    raw = parsed.get("cards")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip() and not contains_emoji(item):
                found.append(item.strip())
    single = parsed.get("text")
    if isinstance(single, str) and single.strip() and not contains_emoji(single):
        found.insert(0, single.strip())
    unique: list[str] = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return tuple(unique[:3])


def _born(profile: object) -> str:
    birth = getattr(profile, "birth_date", None)
    formatted = getattr(birth, "strftime", None)
    if not callable(formatted):
        return "unknown"
    return str(formatted("%d.%m.%Y"))


def _clock(profile: object) -> str:
    if getattr(profile, "birth_time_unknown", False):
        return "unknown"
    clock = getattr(profile, "birth_time", None)
    formatted = getattr(clock, "strftime", None)
    if not callable(formatted):
        return "unknown"
    return str(formatted("%H:%M"))


def _place(profile: object) -> str:
    place = getattr(profile, "birth_place", None)
    if not isinstance(place, str) or place.strip() == "":
        return "unknown"
    return place


def _sun(profile: object) -> str:
    birth = getattr(profile, "birth_date", None)
    if not isinstance(birth, date):
        return "unknown"
    return calendar_sign(birth)


def _next_midnight(moment: datetime, zone_name: str) -> datetime:
    zone = ZoneInfo(zone_name)
    local = moment.astimezone(zone)
    return datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=zone)
