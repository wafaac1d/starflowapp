"""Начало ретроградного хода. Точность бисекции — один час, теория Мошье.

Это не астрономический ежегодник. Станция — первый час, где скорость
планеты уже отрицательная. Уведомление смотрит на календарную дату станции
в DEFAULT_TIMEZONE: за три дня и в день начала.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

PLANETS: tuple[str, ...] = ("меркурий", "венера", "марс")
PRECISION = timedelta(hours=1)
_STEP = timedelta(hours=12)


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
