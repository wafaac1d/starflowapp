import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from starflow.ai.catalog import load_prompts
from starflow.cache.ttl import CachedValue, TtlCache
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.stations import find_retro_periods
from starflow.services.ops import OpsService

MOMENT = datetime(2026, 11, 18, 12, tzinfo=UTC)
PROMPTS_PATH = Path(__file__).resolve().parents[2] / "resources" / "prompts" / "forecasts.yaml"
MERCURY_START = datetime(2026, 11, 9, 12, tzinfo=UTC)
MERCURY_END = datetime(2026, 11, 29, 12, tzinfo=UTC)
VENUS_START = datetime(2026, 12, 5, 12, tzinfo=UTC)
VENUS_END = datetime(2026, 12, 25, 12, tzinfo=UTC)
SATURN_START = MOMENT - timedelta(days=300)
SATURN_END = MOMENT + timedelta(days=40)


def _speed(moment: datetime, planet: str) -> float:
    if planet == "меркурий" and MERCURY_START <= moment < MERCURY_END:
        return -1.0
    if planet == "венера" and VENUS_START <= moment < VENUS_END:
        return -1.0
    if planet == "сатурн" and SATURN_START <= moment < SATURN_END:
        return -1.0
    return 1.0


def test_retro_periods_keep_current_and_upcoming_edges() -> None:
    found = {item.planet: item for item in find_retro_periods(_speed, MOMENT)}
    mercury = found["меркурий"]
    venus = found["венера"]
    saturn = found["сатурн"]
    assert timedelta(0) <= mercury.start - MERCURY_START <= timedelta(hours=1)
    assert timedelta(0) <= mercury.end - MERCURY_END <= timedelta(hours=1)
    assert venus.start > MOMENT
    assert timedelta(0) <= saturn.start - SATURN_START <= timedelta(hours=1)
    assert "марс" not in found


class _Body:
    def __init__(self, name: str, speed: float) -> None:
        self.name = name
        self.speed = speed


class _Sky:
    def __init__(self) -> None:
        self.calls = 0

    def positions(self, moment: datetime) -> tuple[object, ...]:
        self.calls += 1
        names = (
            "меркурий",
            "венера",
            "марс",
            "юпитер",
            "сатурн",
            "уран",
            "нептун",
            "плутон",
        )
        return tuple(_Body(name, _speed(moment, name)) for name in names)


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
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> CachedValue:
        del kind
        found = self.rows.get(key)
        if found is None:
            found = CachedValue(payload, expires_at)
            self.rows[key] = found
        return found

    async def overwrite(
        self,
        key: str,
        kind: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> CachedValue:
        del kind
        stored = CachedValue(payload, expires_at)
        self.rows[key] = stored
        return stored


def _service(cache: TwoLevelCache, sky: _Sky) -> OpsService:
    def unused() -> object:
        raise AssertionError("retrograde cache does not open a unit of work")

    return OpsService(
        unused,
        object(),
        cache,
        object(),
        sky,
        zone_name="Europe/Moscow",
        locale="ru",
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
        clock=lambda: MOMENT,
    )


@pytest.mark.asyncio
async def test_retrograde_periods_are_computed_once_per_day() -> None:
    sky = _Sky()
    store = _Store()
    first = _service(TwoLevelCache(TtlCache(4), store, clock=lambda: MOMENT), sky)
    periods = await first.retrograde_periods()
    counted = sky.calls
    assert counted > 0
    by_planet = {planet: (start, end) for planet, start, end in periods}
    assert by_planet["меркурий"] == ("2026-11-09", "2026-11-29")
    assert by_planet["венера"][0] == "2026-12-05"
    second = _service(TwoLevelCache(TtlCache(4), store, clock=lambda: MOMENT), sky)
    again = await second.retrograde_periods()
    assert again == periods
    assert sky.calls == counted


class _MockProfile:
    def __init__(self) -> None:
        from datetime import date, time

        self.birth_date = date(1995, 8, 12)
        self.birth_time = time(14, 30)
        self.birth_time_unknown = False
        self.birth_place = "Москва"
        self.timezone = "Europe/Moscow"


class _MockProfiles:
    async def ensure(self, _user_id: object) -> _MockProfile:
        return _MockProfile()


class _MockSubscriptions:
    def __init__(self, active: bool) -> None:
        self.active = active

    async def has_active(self, _user_id: object, _moment: datetime) -> bool:
        return self.active


class _MockAiRequests:
    async def add(self, *_args: object) -> None:
        pass


class _MockRetroStore:
    def __init__(self, premium: bool) -> None:
        self.profiles = _MockProfiles()
        self.subscriptions = _MockSubscriptions(premium)
        self.ai_requests = _MockAiRequests()

    async def commit(self) -> None:
        pass


class _MockRetroWork:
    def __init__(self, premium: bool) -> None:
        self._store = _MockRetroStore(premium)

    async def __aenter__(self) -> _MockRetroStore:
        return self._store

    async def __aexit__(self, *_args: object) -> None:
        pass


class _MockStars:
    def __init__(self, owned_keys: set[str]) -> None:
        self.owned_keys = owned_keys

    async def owns(self, _user_id: object, feature: str, subject: str) -> bool:
        return f"{feature}:{subject}" in self.owned_keys


class _MockModel:
    async def complete_forecast(self, **_kwargs: object) -> object:
        from starflow.ai.client import ModelReply

        return ModelReply(
            content=(
                '{"title":"Персональный разбор",'
                '"body":"Текст о Меркурии",'
                '"advice":"Будьте внимательны"}'
            ),
            model="deepseek-flash",
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=100,
        )


@pytest.mark.asyncio
async def test_retro_meaning_premium_and_free_flow() -> None:
    from uuid import uuid4

    from starflow.domain.errors import FieldInvalid
    from starflow.services.retro import RetroService

    prompts = load_prompts(PROMPTS_PATH)
    user_id = uuid4()
    today_dt = datetime(2026, 11, 15, 12, tzinfo=UTC)  # Inside 2026-11-09 to 2026-11-29

    def make_cache() -> TwoLevelCache:
        return TwoLevelCache(TtlCache(16), _Store(), clock=lambda: today_dt)

    # 1. Premium user gets access="allowed"
    premium_service = RetroService(
        lambda: _MockRetroWork(premium=True),  # type: ignore[arg-type]
        make_cache(),
        _MockModel(),  # type: ignore[arg-type]
        prompts,
        model_name="deepseek-flash",
        zone_name="Europe/Moscow",
        stars=_MockStars(set()),
        clock=lambda: today_dt,
    )
    res_prem = await premium_service.meaning(user_id, "меркурий", "2026-11-09", "2026-11-29")
    assert res_prem.access == "allowed"
    assert res_prem.price == 15
    assert res_prem.title == "Персональный разбор"
    assert res_prem.body == "Текст о Меркурии"
    assert res_prem.advice == "Будьте внимательны"

    # 2. Free user without purchase gets access="stars_required"
    free_service = RetroService(
        lambda: _MockRetroWork(premium=False),  # type: ignore[arg-type]
        make_cache(),
        _MockModel(),  # type: ignore[arg-type]
        prompts,
        model_name="deepseek-flash",
        zone_name="Europe/Moscow",
        stars=_MockStars(set()),
        clock=lambda: today_dt,
    )
    res_free = await free_service.meaning(user_id, "меркурий", "2026-11-09", "2026-11-29")
    assert res_free.access == "stars_required"
    assert res_free.price == 15
    assert res_free.body == ""
    assert res_free.advice == ""

    # 3. Free user who purchased for this period gets access="allowed"
    owned = {"retrograde:меркурий:2026-11-09"}
    paid_service = RetroService(
        lambda: _MockRetroWork(premium=False),  # type: ignore[arg-type]
        make_cache(),
        _MockModel(),  # type: ignore[arg-type]
        prompts,
        model_name="deepseek-flash",
        zone_name="Europe/Moscow",
        stars=_MockStars(owned),
        clock=lambda: today_dt,
    )
    res_paid = await paid_service.meaning(user_id, "меркурий", "2026-11-09", "2026-11-29")
    assert res_paid.access == "allowed"
    assert res_paid.body != ""

    # 4. A paid period stays open after it ends. The next period has another start date.
    ended_dt = datetime(2026, 12, 1, 12, tzinfo=UTC)
    ended_service = RetroService(
        lambda: _MockRetroWork(premium=False),  # type: ignore[arg-type]
        TwoLevelCache(TtlCache(16), _Store(), clock=lambda: ended_dt),
        _MockModel(),  # type: ignore[arg-type]
        prompts,
        model_name="deepseek-flash",
        zone_name="Europe/Moscow",
        stars=_MockStars(owned),
        clock=lambda: ended_dt,
    )
    res_ended = await ended_service.meaning(user_id, "меркурий", "2026-11-09", "2026-11-29")
    assert res_ended.access == "allowed"
    assert res_ended.body != ""

    # 5. Invalid planet and dates validation
    with pytest.raises(FieldInvalid, match=re.escape("errors.validation")):
        await free_service.meaning(user_id, "неизвестная_планета", "2026-11-09", "2026-11-29")

    with pytest.raises(FieldInvalid, match=re.escape("errors.date_invalid")):
        await free_service.meaning(user_id, "меркурий", "не_дата", "2026-11-29")
