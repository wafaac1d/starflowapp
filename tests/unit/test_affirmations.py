"""Тесты аффирмаций: один бесплатный расчёт в день и платные категории."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from starflow.ai.catalog import PromptSpec
from starflow.ai.client import ModelReply
from starflow.cache.ttl import CachedValue, TtlCache
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.affirmations import category_label
from starflow.domain.errors import FieldInvalid
from starflow.domain.stars import AFFIRMATION_STARS, affirmation_subject
from starflow.services.affirmations import AffirmationsService

USER = UUID(int=8)
MOMENT = datetime(2026, 10, 29, 12, tzinfo=UTC)


class _Profile:
    birth_date = date(1995, 8, 12)
    birth_time = None
    birth_time_unknown = True
    timezone = "Europe/Moscow"


class _Profiles:
    async def ensure(self, _user_id: UUID) -> _Profile:
        return _Profile()


class _Requests:
    async def add(self, *_args: object, **_kwargs: object) -> UUID:
        return UUID(int=2)


class _Subscriptions:
    def __init__(self, active: bool) -> None:
        self.active = active

    async def has_active(self, _user_id: UUID, _now: datetime) -> bool:
        return self.active


class _Stars:
    def __init__(self, owned: bool) -> None:
        self.owned = owned
        self.seen: list[str] = []

    async def owns(self, _user_id: UUID, feature: str, subject: str) -> bool:
        self.seen.append(f"{feature}:{subject}")
        return self.owned


class _History:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str, date], dict[str, object]] = {}

    async def find(
        self, user_id: UUID, kind: str, period_date: date
    ) -> tuple[UUID, dict[str, object]] | None:
        found = self.rows.get((user_id, kind, period_date))
        if found is None:
            return None
        return UUID(int=1), found

    async def add(
        self, user_id: UUID, kind: str, period_date: date, payload: dict[str, object]
    ) -> UUID:
        self.rows[(user_id, kind, period_date)] = payload
        return UUID(int=1)


class _Db:
    def __init__(self, premium: bool, history: _History) -> None:
        self.profiles = _Profiles()
        self.ai_requests = _Requests()
        self.subscriptions = _Subscriptions(premium)
        self.forecast_history = history

    async def commit(self) -> None:
        return None


def _work(premium: bool, history: _History) -> type:
    class _Work:
        async def __aenter__(self) -> _Db:
            return _Db(premium, history)

        async def __aexit__(self, *_args: object) -> None:
            return None

    return _Work


class _Store:
    def __init__(self) -> None:
        self.rows: dict[str, CachedValue] = {}

    async def read(self, key: str, now: datetime) -> CachedValue | None:
        found = self.rows.get(key)
        if found is None or found.expires_at <= now:
            return None
        return found

    async def note_hit(self, key: str, now: datetime) -> CachedValue | None:
        return await self.read(key, now)

    async def write(
        self, key: str, kind: str, payload: dict[str, object], expires_at: datetime
    ) -> CachedValue:
        del kind
        found = CachedValue(payload, expires_at)
        self.rows[key] = found
        return found

    async def overwrite(
        self, key: str, kind: str, payload: dict[str, object], expires_at: datetime
    ) -> CachedValue:
        del kind
        stored = CachedValue(payload, expires_at)
        self.rows[key] = stored
        return stored


class _Model:
    async def complete_forecast(self, **_kwargs: object) -> ModelReply:
        content = '{"text":"Я доверяю себе.","category":"for_you"}'
        return ModelReply(content, "deepseek-flash", 1, 1, 1)


class _Prompts:
    def get(self, _name: str) -> PromptSpec:
        return PromptSpec("fast", "system", "user", 1, 0.5, 400, "json_object")


def _service(
    *,
    premium: bool = False,
    stars: _Stars | None = None,
    clock: Callable[[], datetime] | None = None,
    history: _History | None = None,
) -> AffirmationsService:
    shared_history = history or _History()
    work = _work(premium, shared_history)
    current_clock = clock or (lambda: MOMENT)
    cache = TwoLevelCache(TtlCache(8), _Store(), clock=current_clock)
    return AffirmationsService(
        work,
        cache,
        _Model(),
        _Prompts(),  # type: ignore[arg-type]
        model_name="deepseek-flash",
        zone_name="Europe/Moscow",
        stars=stars,
        clock=current_clock,
    )


def test_domain_rules() -> None:
    assert category_label("for_you") == "Для вас"
    assert category_label("confidence") == "Уверенность"
    assert category_label("calm") == "Спокойствие"
    with pytest.raises(FieldInvalid):
        category_label("magic")
    assert affirmation_subject("for_you") == "for_you"
    with pytest.raises(ValueError):
        affirmation_subject("unknown")


@pytest.mark.asyncio
async def test_affirmations_free_limit_and_locked_second_category() -> None:
    history = _History()
    service = _service(history=history)

    # 1. First category today -> preview with 1 free card
    first = await service.get_affirmations(USER, "for_you")
    assert first.category == "for_you"
    assert first.access == "preview"
    assert first.price == AFFIRMATION_STARS
    assert len(first.cards) == 1

    # 2. Status shows chosen category
    st = await service.status(USER)
    assert st.chosen_category == "for_you"
    assert st.chosen_label == "Для вас"
    assert st.is_premium is False

    # 3. Same category again -> same preview
    again = await service.get_affirmations(USER, "for_you")
    assert again.access == "preview"
    assert len(again.cards) == 1

    # 4. Different category on the same day -> locked!
    second = await service.get_affirmations(USER, "confidence")
    assert second.access == "locked"
    assert second.price == AFFIRMATION_STARS
    assert second.cards == ()
    assert second.free_chosen_label == "Для вас"


@pytest.mark.asyncio
async def test_affirmations_next_day_allows_new_choice() -> None:
    time_state = {"now": MOMENT}
    history = _History()
    service = _service(clock=lambda: time_state["now"], history=history)

    # Day 1: for_you
    d1 = await service.get_affirmations(USER, "for_you")
    assert d1.access == "preview"

    # Advance 1 day
    time_state["now"] = MOMENT + timedelta(days=1)
    st = await service.status(USER)
    assert st.chosen_category is None

    # Day 2: calm is free
    d2 = await service.get_affirmations(USER, "calm")
    assert d2.access == "preview"
    assert d2.label == "Спокойствие"


@pytest.mark.asyncio
async def test_affirmations_premium_and_paid_unlimited() -> None:
    # Premium user
    service_prem = _service(premium=True)
    prem = await service_prem.get_affirmations(USER, "for_you")
    assert prem.access == "full"
    assert prem.price == 0
    assert len(prem.cards) == 3

    # User who paid stars for the category
    stars = _Stars(owned=True)
    service_paid = _service(stars=stars)
    paid = await service_paid.get_affirmations(USER, "confidence")
    assert paid.access == "full"
    assert paid.price == 0
    assert len(paid.cards) == 3
    assert stars.seen == ["affirmation:confidence"]
