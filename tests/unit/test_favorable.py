"""Благоприятные дни: проверка ответа модели и один вызов на сутки."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from starflow.ai.catalog import load_prompts
from starflow.ai.client import ModelReply
from starflow.cache.ttl import CachedValue, TtlCache
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.errors import FieldInvalid
from starflow.domain.favorable import accept_favorable, favorable_subject, nearest_favorable
from starflow.services.favorable import FavorableService

USER = UUID(int=7)
MOMENT = datetime(2026, 10, 28, 12, tzinfo=UTC)
PROMPTS = load_prompts(
    Path(__file__).resolve().parents[2] / "resources" / "prompts" / "forecasts.yaml"
)
GOOD = """
{"days":[
  {"date":"2026-10-12","start":"10:00","end":"13:00","note":"Для спокойного разговора."},
  {"date":"2026-10-15","start":"16:00","end":"18:00","note":"Вечер без спешки."},
  {"date":"2026-11-01","start":"10:00","end":"12:00","note":"Чужой месяц."}
]}
"""


def test_favorable_days_stay_inside_the_month_and_keep_a_real_window() -> None:
    accepted = accept_favorable(2026, 10, _json(GOOD))
    assert accepted is not None
    assert [item.date for item in accepted] == ["2026-10-12", "2026-10-15"]
    assert (
        accept_favorable(
            2026,
            10,
            {"days": [{"date": "2026-10-12", "start": "13:00", "end": "10:00", "note": "Нет."}]},
        )
        is None
    )
    assert accept_favorable(2026, 10, {"title": "нет дней"}) is None
    assert nearest_favorable(accepted, "2026-10-13")[0].date == "2026-10-15"
    assert nearest_favorable(accepted, "2026-10-28")[0].date == "2026-10-15"
    assert favorable_subject("2026-10", "meeting", "") == "2026-10:meeting:встреча"
    assert favorable_subject("2026-10", "custom", "День рождения") == "2026-10:custom:день-рождения"


class _Profile:
    birth_date = date(1995, 8, 12)
    birth_time = time(14, 30)
    birth_time_unknown = False
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
        key = (user_id, kind, period_date)
        found = self.rows.get(key)
        if found is None:
            return None
        return UUID(int=1), found

    async def add(
        self, user_id: UUID, kind: str, period_date: date, payload: dict[str, object]
    ) -> UUID:
        self.rows[(user_id, kind, period_date)] = payload
        return UUID(int=1)


class _Db:
    def __init__(self, premium: bool, history: _History | None = None) -> None:
        self.profiles = _Profiles()
        self.ai_requests = _Requests()
        self.subscriptions = _Subscriptions(premium)
        self.forecast_history = history or _History()

    async def commit(self) -> None:
        return None


def _work(premium: bool, history: _History | None = None) -> type:
    shared_history = history or _History()

    class _Work:
        async def __aenter__(self) -> _Db:
            return _Db(premium, shared_history)

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
        found = self.rows.get(key)
        if found is None:
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
    def __init__(self, scripts: list[str]) -> None:
        self.scripts = scripts
        self.calls = 0
        self.seen: list[str] = []

    async def complete_forecast(self, **kwargs: object) -> ModelReply:
        self.calls += 1
        user = kwargs["user"]
        assert isinstance(user, str)
        self.seen.append(user)
        content = self.scripts.pop(0)
        return ModelReply(content, "deepseek-flash", 1, 1, 1)


def _service(
    model: _Model,
    *,
    premium: bool = False,
    stars: _Stars | None = None,
    clock: Callable[[], datetime] | None = None,
    history: _History | None = None,
) -> FavorableService:
    shared_history = history or _History()
    work = _work(premium, shared_history)
    current_clock = clock or (lambda: MOMENT)
    cache = TwoLevelCache(TtlCache(8), _Store(), clock=current_clock)
    return FavorableService(
        work,
        cache,
        model,
        PROMPTS,
        model_name="deepseek-flash",
        zone_name="Europe/Moscow",
        stars=stars,
        clock=current_clock,
    )


def _json(text: str) -> object:
    return json.loads(text)


async def test_one_model_call_serves_the_same_month_again() -> None:
    model = _Model([GOOD, GOOD])
    service = _service(model)
    status_before = await service.status(USER)
    assert status_before.chosen_event is None
    assert status_before.is_premium is False

    first = await service.month(USER, "2026-10", "meeting", "")
    second = await service.month(USER, "2026-10", "meeting", "")
    assert first.status == "ready"
    assert first.access == "preview"
    assert first.price == 30
    assert [item.date for item in first.days] == ["2026-10-15"]
    assert second.days == first.days
    assert model.calls == 1
    assert "12.08.1995" in model.seen[0]
    assert "14:30" in model.seen[0]
    assert "Встреча" in model.seen[0]

    status_after = await service.status(USER)
    assert status_after.chosen_event == "meeting"
    assert status_after.chosen_label == "Встреча"

    trip = await service.month(USER, "2026-10", "trip", "")
    assert trip.status == "ready"
    assert trip.access == "locked"
    assert trip.price == 30
    assert trip.days == ()
    assert trip.free_chosen_label == "Встреча"
    assert model.calls == 1


async def test_next_day_allows_a_new_free_category() -> None:
    time_state = {"now": MOMENT}
    history = _History()
    model = _Model([GOOD, GOOD])
    service = _service(model, clock=lambda: time_state["now"], history=history)

    first = await service.month(USER, "2026-10", "meeting", "")
    assert first.access == "preview"
    assert [item.date for item in first.days] == ["2026-10-15"]

    time_state["now"] = MOMENT + timedelta(days=1)
    status_next = await service.status(USER)
    assert status_next.chosen_event is None

    trip = await service.month(USER, "2026-10", "trip", "")
    assert trip.access == "preview"
    assert [item.date for item in trip.days] == ["2026-10-15"]


async def test_premium_and_a_paid_month_show_every_day() -> None:
    opened = await _service(_Model([GOOD]), premium=True).month(USER, "2026-10", "meeting", "")
    assert opened.access == "full"
    assert opened.price == 0
    assert [item.date for item in opened.days] == ["2026-10-12", "2026-10-15"]
    stars = _Stars(True)
    paid = await _service(_Model([GOOD]), stars=stars).month(USER, "2026-10", "meeting", "")
    assert paid.access == "full"
    assert [item.date for item in paid.days] == ["2026-10-12", "2026-10-15"]
    assert stars.seen == ["favorable:2026-10:meeting:встреча"]


async def test_a_broken_reply_is_repaired_once() -> None:
    model = _Model(["не json", GOOD])
    view = await _service(model).month(USER, "2026-10", "purchase", "")
    assert view.status == "ready"
    assert view.label == "Покупка"
    assert model.calls == 2


async def test_unknown_event_is_rejected() -> None:
    model = _Model([GOOD])
    with pytest.raises(FieldInvalid):
        await _service(model).month(USER, "2026-10", "party", "")
    assert model.calls == 0
