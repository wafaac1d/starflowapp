"""Местное время, пары прогрева, streak и точность станции без базы."""

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from starflow.ai.catalog import load_prompts
from starflow.ai.client import ModelReply
from starflow.cache.two_level import CacheHit
from starflow.domain.notify_clock import SLOTS, is_due, parse_slot, warm_window
from starflow.domain.segments import forecast_cache_key, pair_segment, period_key
from starflow.domain.stations import find_stations
from starflow.domain.streak import next_streak
from starflow.domain.warmup_plan import SIGNS, WARM_BUDGET, unordered_pairs
from starflow.scheduler.runtime import SchedulerRuntime
from starflow.services.ops import OpsService
from tests.support import make_settings

RESOURCES = Path(__file__).resolve().parents[2] / "resources"
ROOT_PROMPTS = load_prompts(RESOURCES / "prompts" / "forecasts.yaml")


def test_slots_catch_up_and_dst_folds() -> None:
    with pytest.raises(ValueError, match="slot"):
        parse_slot("09:15")
    assert len(SLOTS) == 48
    zone = "Europe/Berlin"
    morning = datetime(2026, 6, 15, 7, 20, tzinfo=UTC)
    assert is_due(morning, zone, time(9, 0)) is True
    assert is_due(datetime(2026, 6, 15, 6, 59, tzinfo=UTC), zone, time(9, 0)) is False
    assert is_due(datetime(2026, 6, 15, 10, 0, tzinfo=UTC), zone, time(9, 0)) is False
    spring = datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert is_due(spring, zone, time(2, 30)) is True
    assert is_due(datetime(2026, 3, 29, 0, 30, tzinfo=UTC), zone, time(2, 30)) is False
    first = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    second = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    assert is_due(first, zone, time(2, 30)) is True
    assert is_due(second, zone, time(2, 30)) is True
    berlin = ZoneInfo(zone)
    assert first.astimezone(berlin).date() == second.astimezone(berlin).date()


def test_warm_pairs_and_streak() -> None:
    pairs = unordered_pairs()
    assert len(pairs) == 78
    assert len(set(pairs)) == 78
    assert ("овен", "овен") in pairs
    assert ("овен", "рыбы") in pairs
    assert ("рыбы", "овен") not in pairs
    assert len(SIGNS) == 12
    assert next_streak(None, date(2026, 6, 2), 4) == 1
    assert next_streak(date(2026, 6, 1), date(2026, 6, 2), 4) == 5
    assert next_streak(date(2026, 6, 2), date(2026, 6, 2), 4) == 4
    assert next_streak(date(2026, 6, 1), date(2026, 6, 3), 4) == 1
    moment = datetime(2026, 6, 15, 3, 0, tzinfo=UTC)
    assert warm_window(moment, "Europe/Moscow") is True
    assert warm_window(datetime(2026, 6, 15, 1, 0, tzinfo=UTC), "Europe/Moscow") is False
    assert warm_window(datetime(2026, 6, 15, 5, 0, tzinfo=UTC), "Europe/Moscow") is False


def test_station_search_stops_within_an_hour() -> None:
    boundary = datetime(2026, 6, 18, 0, tzinfo=UTC)

    def speed_at(moment: datetime, planet: str) -> float:
        if planet != "меркурий":
            return 1.0
        return -1.0 if moment >= boundary else 1.0

    found = [
        item
        for item in find_stations(
            speed_at,
            boundary - timedelta(days=2),
            boundary + timedelta(days=2),
        )
        if item.planet == "меркурий"
    ]
    assert len(found) == 1
    delta = found[0].start - boundary
    assert timedelta(0) <= delta <= timedelta(hours=1)
    assert speed_at(found[0].start, "меркурий") < 0


class _Model:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_forecast(self, **_kwargs: object) -> ModelReply:
        self.calls += 1
        return ModelReply(
            content='{"title":"день","body":"короткий текст"}',
            model="deepseek-flash",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
        )


class _Cache:
    def __init__(self, ready: set[str]) -> None:
        self.ready = ready

    async def get_or_create(
        self,
        key: str,
        _kind: str,
        expires: datetime,
        producer: object,
    ) -> CacheHit:
        if key in self.ready:
            return CacheHit({}, expires, False)
        if not callable(producer):
            raise AssertionError(key)
        await producer()
        return CacheHit({}, expires, True)


class _Speed:
    def positions(self, _moment: datetime) -> tuple[object, ...]:
        return ()


@pytest.mark.asyncio
async def test_warmup_stops_at_the_budget_and_skips_a_cached_key() -> None:
    moment = datetime(2026, 6, 15, 3, 0, tzinfo=UTC)
    service = OpsService(
        lambda: None,  # type: ignore[arg-type]
        ROOT_PROMPTS,
        _Cache(set()),  # type: ignore[arg-type]
        _Model(),
        _Speed(),
        zone_name="Europe/Moscow",
        locale="ru",
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
        clock=lambda: moment,
    )
    cached = service
    model = _Model()
    ready: set[str] = set()
    cache = _Cache(ready)
    cached._model = model  # type: ignore[assignment]
    cached._cache = cache  # type: ignore[assignment]
    pairs = unordered_pairs()
    period = period_key("compatibility", moment, "Europe/Moscow")
    left, right = pairs[0]
    ready.add(
        forecast_cache_key(
            "compatibility",
            period,
            pair_segment(left, right),
            "",
            "ru",
            ROOT_PROMPTS.get("compatibility").version,
        )
    )
    made = await cached.warm_pairs(moment)
    assert model.calls == WARM_BUDGET
    assert made == WARM_BUDGET


@pytest.mark.asyncio
async def test_scheduler_bounds_and_shutdown() -> None:
    runtime = SchedulerRuntime(
        make_settings(),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    runtime.start()
    jobs = {job.id: job for job in runtime._scheduler.get_jobs()}
    assert set(jobs) == {
        "notification_outbox",
        "notification_plan",
        "cache_warmup",
        "retention",
        "billing_maintain",
    }
    for job in jobs.values():
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.misfire_grace_time == 60
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_morning_and_evening_daily_variations_across_seven_days() -> None:
    from uuid import uuid4

    from starflow.cache.memory import MemoryCache
    from starflow.i18n.catalog import load_catalog
    from starflow.i18n.guard import contains_emoji

    catalog = load_catalog(RESOURCES, "ru", MemoryCache(8))

    morning_texts: set[str] = set()
    evening_texts: set[str] = set()

    for day_num in range(1, 8):
        m_key = f"bot.day_ready_{day_num}"
        e_key = f"bot.tomorrow_ready_{day_num}"

        m_text = catalog.text(m_key)
        e_text = catalog.text(e_key)

        assert m_text.strip() != ""
        assert e_text.strip() != ""
        assert not contains_emoji(m_text)
        assert not contains_emoji(e_text)

        morning_texts.add(m_text)
        evening_texts.add(e_text)

    # All 7 morning texts and 7 evening texts must be distinct
    assert len(morning_texts) == 7
    assert len(evening_texts) == 7

    class _MockOutbox:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        async def enqueue(
            self,
            user_id: object,
            kind: str,
            text_key: str,
            local_date: date,
            scheduled_for: datetime,
            **kwargs: object,
        ) -> None:
            self.records.append(
                {
                    "user_id": user_id,
                    "kind": kind,
                    "text_key": text_key,
                    "local_date": local_date,
                    "scheduled_for": scheduled_for,
                    **kwargs,
                }
            )

    class _MockUow:
        def __init__(self) -> None:
            self.outbox = _MockOutbox()

    service = OpsService(
        lambda: None,  # type: ignore[arg-type]
        ROOT_PROMPTS,
        _Cache(set()),  # type: ignore[arg-type]
        _Model(),
        _Speed(),
        zone_name="Europe/Moscow",
        locale="ru",
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
    )

    uow = _MockUow()
    user_id = uuid4()
    moment = datetime(2026, 6, 15, 6, 0, tzinfo=UTC)  # Monday: weekday 0, day 1

    # Check 7 consecutive days starting from Monday 2026-06-15
    for offset in range(7):
        current_day = date(2026, 6, 15) + timedelta(days=offset)
        expected_day_num = offset + 1

        # Morning notice (ready)
        await service._notice(
            uow,  # type: ignore[arg-type]
            user_id,
            "day",
            current_day,
            moment,
            "reading/day",
            ready=True,
        )
        assert uow.outbox.records[-1]["text_key"] == f"bot.day_ready_{expected_day_num}"

        # Evening notice (ready)
        await service._notice(
            uow,  # type: ignore[arg-type]
            user_id,
            "tomorrow",
            current_day,
            moment,
            "forecast?period=tomorrow",
            ready=True,
        )
        assert uow.outbox.records[-1]["text_key"] == f"bot.tomorrow_ready_{expected_day_num}"

    # Fallbacks remain constant
    await service._notice(
        uow,  # type: ignore[arg-type]
        user_id,
        "day",
        date(2026, 6, 15),
        moment,
        "reading/day",
        ready=False,
    )
    assert uow.outbox.records[-1]["text_key"] == "bot.day_fallback"

    await service._notice(
        uow,  # type: ignore[arg-type]
        user_id,
        "tomorrow",
        date(2026, 6, 15),
        moment,
        "forecast?period=tomorrow",
        ready=False,
    )
    assert uow.outbox.records[-1]["text_key"] == "bot.tomorrow_fallback"

    # Moon notice remains bot.moon_ready
    await service._notice(
        uow,  # type: ignore[arg-type]
        user_id,
        "moon",
        date(2026, 6, 15),
        moment,
        "reading/moon",
        ready=True,
    )
    assert uow.outbox.records[-1]["text_key"] == "bot.moon_ready"


@pytest.mark.asyncio
async def test_ops_preferences_default_enabled_for_new_users() -> None:
    from uuid import uuid4

    class _MockSettingsRepo:
        async def read(self, _user_id: object) -> None:
            return None

    class _MockProfilesRepo:
        async def get_by_user_id(self, _user_id: object) -> None:
            return None

    class _MockStore:
        notification_settings = _MockSettingsRepo()
        profiles = _MockProfilesRepo()

    class _MockWork:
        async def __aenter__(self) -> _MockStore:
            return _MockStore()

        async def __aexit__(self, *_args: object) -> None:
            pass

    service = OpsService(
        lambda: _MockWork(),  # type: ignore[arg-type]
        ROOT_PROMPTS,
        _Cache(set()),  # type: ignore[arg-type]
        _Model(),
        _Speed(),
        zone_name="Europe/Moscow",
        locale="ru",
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
    )
    local_time, zone, day, moon, retro = await service.preferences(uuid4())
    assert local_time == "09:00"
    assert zone == "Europe/Moscow"
    assert day is True
    assert moon is True
    assert retro is True


