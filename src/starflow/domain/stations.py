"""Начало ретроградного хода. Точность бисекции — один час, теория Мошье.

Это не астрономический ежегодник. Станция — первый час, где скорость
планеты уже отрицательная. Уведомление смотрит на календарную дату станции
в DEFAULT_TIMEZONE: за три дня и в день начала.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

PLANETS: tuple[str, ...] = ("меркурий", "венера", "марс")
RETROGRADE_PLANETS: tuple[str, ...] = (
    "меркурий",
    "венера",
    "марс",
    "юпитер",
    "сатурн",
    "уран",
    "нептун",
    "плутон",
)
PRECISION = timedelta(hours=1)
_STEP = timedelta(hours=12)
_LOOKBACK = timedelta(days=220)
_LOOKAHEAD = timedelta(days=220)
_EXTRA = timedelta(days=220)


@dataclass(frozen=True)
class Station:
    planet: str
    start: datetime


def find_stations(
    speed_at: Callable[[datetime, str], float],
    start: datetime,
    end: datetime,
) -> tuple[Station, ...]:
    found: list[Station] = []
    for planet in PLANETS:
        found.extend(_planet(speed_at, planet, start, end))
    return tuple(found)


def _planet(
    speed_at: Callable[[datetime, str], float],
    planet: str,
    start: datetime,
    end: datetime,
) -> list[Station]:
    stations: list[Station] = []
    previous = start
    previous_speed = speed_at(previous, planet)
    cursor = start + _STEP
    while cursor <= end:
        current = speed_at(cursor, planet)
        if previous_speed >= 0 and current < 0:
            stations.append(Station(planet, _refine(speed_at, planet, previous, cursor)))
        previous = cursor
        previous_speed = current
        cursor += _STEP
    return stations


def _refine(
    speed_at: Callable[[datetime, str], float],
    planet: str,
    earlier: datetime,
    later: datetime,
) -> datetime:
    left = earlier
    right = later
    while right - left > PRECISION:
        middle = left + (right - left) / 2
        if speed_at(middle, planet) < 0:
            right = middle
        else:
            left = middle
    return right


@dataclass(frozen=True)
class RetroPeriod:
    planet: str
    start: datetime
    end: datetime


def find_retro_periods(
    speed_at: Callable[[datetime, str], float],
    now: datetime,
) -> tuple[RetroPeriod, ...]:
    """Текущие и будущие отрезки. Конец, который уже прошёл, не возвращается."""
    window_start = now - _LOOKBACK
    window_end = now + _LOOKAHEAD
    found: list[RetroPeriod] = []
    for planet in RETROGRADE_PLANETS:
        found.extend(_periods(speed_at, planet, window_start, window_end))
    kept = [
        item for item in found if item.end > now - timedelta(days=1) and item.start <= window_end
    ]
    return tuple(kept)


def _periods(
    speed_at: Callable[[datetime, str], float],
    planet: str,
    start: datetime,
    end: datetime,
) -> list[RetroPeriod]:
    if speed_at(start, planet) < 0:
        probe = start
        floor = start - _EXTRA
        while probe > floor and speed_at(probe, planet) < 0:
            probe -= _STEP
        if speed_at(probe, planet) < 0:
            return []
        open_start: datetime | None = _refine(speed_at, planet, probe, probe + _STEP)
        previous = probe + _STEP
        negative = True
    else:
        open_start = None
        previous = start
        negative = False
    periods: list[RetroPeriod] = []
    cursor = previous + _STEP
    limit = end + _EXTRA
    while cursor <= limit:
        current = speed_at(cursor, planet) < 0
        if not negative and current:
            open_start = _refine(speed_at, planet, previous, cursor)
        elif negative and not current and open_start is not None:
            periods.append(
                RetroPeriod(planet, open_start, _leave(speed_at, planet, previous, cursor))
            )
            open_start = None
        previous = cursor
        negative = current
        cursor += _STEP
        if cursor > end and open_start is None:
            break
    return periods


def _leave(
    speed_at: Callable[[datetime, str], float],
    planet: str,
    earlier: datetime,
    later: datetime,
) -> datetime:
    left = earlier
    right = later
    while right - left > PRECISION:
        middle = left + (right - left) / 2
        if speed_at(middle, planet) < 0:
            left = middle
        else:
            right = middle
    return right
