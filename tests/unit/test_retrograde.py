from datetime import UTC, datetime, timedelta

import pytest

from starflow.cache.ttl import CachedValue, TtlCache
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.stations import find_retro_periods
from starflow.services.ops import OpsService

MOMENT = datetime(2026, 11, 18, 12, tzinfo=UTC)
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
