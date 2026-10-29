"""Сервис аффирмаций на день. Бесплатно доступен один расчёт в день по одной из категорий."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from starflow.ai.catalog import PromptCatalog
from starflow.ai.client import ModelReply
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.affirmations import (
    DEFAULT_AFFIRMATIONS,
    AffirmationCard,
    category_label,
)
from starflow.domain.errors import Conflict
from starflow.domain.stars import AFFIRMATION_STARS, affirmation_subject
from starflow.domain.time import now_utc
from starflow.repositories.sql import (
    AiRequestRepository,
    ForecastHistoryRepository,
    ProfileRepository,
    SubscriptionRepository,
)


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
        is_free = not premium
        if is_free and self._stars is not None:
            subject = affirmation_subject(category)
            owned = await self._stars.owns(user_id, "affirmation", subject)
            if owned:
                is_free = False

        default_cards = DEFAULT_AFFIRMATIONS.get(category, ())

        if is_free:
            async with self._uow_factory() as uow:
                found_hist = await uow.forecast_history.find(user_id, "affirmation", today)
            if found_hist is not None:
                _id, recorded = found_hist
                rec_cat = recorded.get("category")
                rec_label = cast(str, recorded.get("label", ""))
                if rec_cat != category:
                    return AffirmationsView(
                        category=category,
                        label=label,
                        access="locked",
                        price=AFFIRMATION_STARS,
                        cards=(),
                        free_chosen_label=rec_label,
                    )
            else:
                # First time user views an affirmation category today
                async with self._uow_factory() as uow:
                    try:
                        await uow.forecast_history.add(
                            user_id,
                            "affirmation",
                            today,
                            {"category": category, "label": label},
                        )
                        await uow.commit()
                    except Conflict:
                        pass

            # Free user gets 1 affirmation card preview
            preview_cards = (default_cards[0],) if default_cards else ()
            return AffirmationsView(
                category=category,
                label=label,
                access="preview",
                price=AFFIRMATION_STARS,
                cards=preview_cards,
            )

        # Full access (premium or owned via stars)
        return AffirmationsView(
            category=category,
            label=label,
            access="full",
            price=0,
            cards=default_cards,
        )
