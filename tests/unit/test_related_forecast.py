"""Прогноз близкого не подменяет свой и для бесплатного тарифа открывается раз в сутки."""

import asyncio
import json
from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from starflow.ai.catalog import PromptCatalog, PromptSpec
from starflow.ai.client import ModelReply
from starflow.domain.quota import Allowed, PremiumRequired
from starflow.domain.records import Profile, RelatedProfile
from starflow.services.forecast import ForecastService, ReadingScope

USER = UUID(int=1)
MAMA = UUID(int=2)
DANIIL = UUID(int=3)
WHEN = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


class _Work:
    def __init__(self, store: object) -> None:
        self._store = store

    async def __aenter__(self) -> object:
        return self._store

    async def __aexit__(self, *_args: object) -> None:
        return None


class _History:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str, date], tuple[UUID, dict[str, object]]] = {}

    async def find(
        self,
        user_id: UUID,
        kind: str,
        period_date: date,
    ) -> tuple[UUID, dict[str, object]] | None:
        return self.rows.get((user_id, kind, period_date))

    async def add(
        self,
        user_id: UUID,
        kind: str,
        period_date: date,
        payload: dict[str, object],
    ) -> UUID:
        history_id = uuid4()
        self.rows[(user_id, kind, period_date)] = (history_id, payload)
        return history_id

    async def update_payload(self, history_id: UUID, payload: dict[str, object]) -> None:
        for key, (found, _payload) in self.rows.items():
            if found == history_id:
                self.rows[key] = (history_id, payload)

    async def list_for_user(self, user_id: UUID) -> tuple[object, ...]:
        return tuple(
            _Row(history_id, kind, period, payload)
            for (owner, kind, period), (history_id, payload) in self.rows.items()
            if owner == user_id
        )


class _Row:
    def __init__(
        self,
        history_id: UUID,
        kind: str,
        period_date: date,
        payload: dict[str, object],
    ) -> None:
        self.id = history_id
        self.kind = kind
        self.period_date = period_date
        self.payload = payload


class _People:
    def __init__(self, people: dict[UUID, RelatedProfile]) -> None:
        self._people = people

    async def get_owned(self, _user_id: UUID, related_id: UUID) -> RelatedProfile | None:
        return self._people.get(related_id)


class _Profiles:
    async def ensure(self, user_id: UUID) -> Profile:
        return Profile(
            id=UUID(int=9),
            user_id=user_id,
            display_name="Анна",
            birth_date=date(1995, 8, 12),
            birth_time=time(14, 30),
            birth_time_unknown=False,
            birth_place="Москва",
            latitude=None,
            longitude=None,
            timezone="Europe/Moscow",
            onboarding_step="done",
        )


class _Users:
    async def ensure_referral_code(self, _user_id: UUID) -> str:
        return "code"

    async def start_param(self, _user_id: UUID) -> None:
        return None


class _Log:
    async def add(self, *_args: object) -> None:
        return None


class _Store:
    def __init__(self, people: dict[UUID, RelatedProfile]) -> None:
        self.profiles = _Profiles()
        self.related_profiles = _People(people)
        self.forecast_history = _History()
        self.users = _Users()
        self.ai_requests = _Log()

    async def commit(self) -> None:
        return None


class _Quota:
    def __init__(self, *, premium: bool) -> None:
        self._premium = premium

    async def preview(self, _user_id: UUID, feature: str) -> Allowed | PremiumRequired:
        if feature == "related_forecast" and self._premium:
            return Allowed()
        if feature == "related_forecast":
            return PremiumRequired()
        return Allowed()


class _Model:
    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    async def complete_forecast(self, **kwargs: object) -> ModelReply:
        self.calls += 1
        user = kwargs["user"]
        assert isinstance(user, str)
        self.prompts.append(user)
        return ModelReply(
            json.dumps(
                {
                    "title": "Тихий день рядом",
                    "body": "День для спокойных дел и коротких разговоров.",
                }
            ),
            "deepseek-flash",
            1,
            1,
            1,
        )


class _Texts:
    def text(self, key: str) -> str:
        return key


def _person(person_id: UUID, name: str, born: date, *, consent: bool) -> RelatedProfile:
    return RelatedProfile(
        id=person_id,
        display_name=name,
        birth_date=born,
        birth_time=None,
        birth_time_unknown=True,
        birth_place="Советск",
        latitude=None,
        longitude=None,
        consent=consent,
    )


def _service(store: _Store, *, premium: bool) -> tuple[ForecastService, _Model]:
    model = _Model()
    prompt = PromptSpec("day", 3, "fast", 0.2, 400, "json", "system", "Факты: {facts}")
    service = ForecastService(
        lambda: _Work(store),
        object(),
        model,
        PromptCatalog(
            {
                "day": prompt,
                "tomorrow": prompt,
                "week": prompt,
                "personal_month": prompt,
            }
        ),
        _Texts(),
        _Quota(premium=premium),
        object(),
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
        zone_name="Europe/Moscow",
        locale="ru",
        mini_app_url="https://example.test",
        clock=lambda: WHEN,
        background=False,
    )
    return service, model


async def _settle(service: ForecastService) -> None:
    await asyncio.gather(*tuple(service._tasks))


async def test_free_related_forecast_uses_their_birth_and_one_reading_a_day() -> None:
    people = {
        MAMA: _person(MAMA, "Мама", date(1968, 3, 14), consent=True),
        DANIIL: _person(DANIIL, "Даниил", date(1988, 11, 22), consent=True),
    }
    store = _Store(people)
    service, model = _service(store, premium=False)
    scope = ReadingScope(related_id=MAMA)
    assert (await service.start(USER, "day", "related-mama", scope)).status == "pending"
    await _settle(service)
    ready = await service.current(USER, "day", scope)
    assert ready.status == "ready"
    assert ready.body == "День для спокойных дел и коротких разговоров."
    assert model.calls == 1
    assert "14.03.1968" in model.prompts[0]
    assert "12.08.1995" not in model.prompts[0]
    assert "Советск" in model.prompts[0]
    service._jobs.clear()
    again = await service.start(USER, "day", "related-mama-replay", scope)
    assert again.status == "ready"
    assert again.replayed is True
    assert model.calls == 1
    blocked = await service.start(USER, "day", "related-daniil", ReadingScope(related_id=DANIIL))
    assert blocked.status == "limit"
    assert blocked.body == "errors.related_forecast_limit"
    assert model.calls == 1
    history = await service.history(USER)
    assert any(kind.startswith("day:related:") for _history_id, kind, _day, _title in history)
    assert all(kind != "related_forecast" for _history_id, kind, _day, _title in history)


async def test_premium_related_forecasts_are_not_capped() -> None:
    people = {
        MAMA: _person(MAMA, "Мама", date(1968, 3, 14), consent=True),
        DANIIL: _person(DANIIL, "Даниил", date(1988, 11, 22), consent=True),
    }
    store = _Store(people)
    service, model = _service(store, premium=True)
    await service.start(USER, "day", "premium-mama", ReadingScope(related_id=MAMA))
    await _settle(service)
    await service.start(USER, "day", "premium-daniil", ReadingScope(related_id=DANIIL))
    await _settle(service)
    second = await service.current(USER, "day", ReadingScope(related_id=DANIIL))
    assert second.status == "ready"
    assert model.calls == 2


async def test_related_forecast_without_consent_does_not_spend_the_day() -> None:
    people = {MAMA: _person(MAMA, "Мама", date(1968, 3, 14), consent=False)}
    store = _Store(people)
    service, model = _service(store, premium=False)
    scope = ReadingScope(related_id=MAMA)
    assert (await service.start(USER, "day", "related-consent", scope)).status == "pending"
    await _settle(service)
    blocked = await service.current(USER, "day", scope)
    assert blocked.status == "blocked"
    assert blocked.body == "errors.consent_required"
    assert model.calls == 0
    assert store.forecast_history.rows == {}
