"""Локальные положения на теории Мошье.

Сжатые файлы эфемерид в образ не входят. Флаг FLG_MOSEPH запрещает их поиск и
сетевую докачку. Публичный запуск по-прежнему закрыт, пока не выбрана AGPL
на весь сервис или профессиональная лицензия Swiss Ephemeris (D-010, D-032).
Дома — Плацидус. Лунный день — число местных восходов Луны после точного
новолуния; без координат поле пустое.
"""

from datetime import UTC, datetime

import swisseph as swe

_FLAGS = int(swe.FLG_MOSEPH) | int(swe.FLG_SPEED)
_BODIES = (
    (int(swe.SUN), "солнце"),
    (int(swe.MOON), "луна"),
    (int(swe.MERCURY), "меркурий"),
    (int(swe.VENUS), "венера"),
    (int(swe.MARS), "марс"),
    (int(swe.JUPITER), "юпитер"),
    (int(swe.SATURN), "сатурн"),
    (int(swe.URANUS), "уран"),
    (int(swe.NEPTUNE), "нептун"),
    (int(swe.PLUTO), "плутон"),
)


class BodyPosition:
    def __init__(self, name: str, longitude: float, speed: float) -> None:
        self.name = name
        self.longitude = longitude
        self.speed = speed

    @property
    def retrograde(self) -> bool:
        return self.speed < 0


class SwissEphemeris:
    def positions(self, moment: datetime) -> tuple[BodyPosition, ...]:
        julian = _julian(moment)
        found: list[BodyPosition] = []
        for body, name in _BODIES:
            raw = swe.calc_ut(julian, body, _FLAGS)
            coords = raw[0]
            found.append(BodyPosition(name, float(coords[0]), float(coords[3])))
        return tuple(found)

    def houses(
        self,
        moment: datetime,
        latitude: float,
        longitude: float,
    ) -> tuple[float, tuple[float, ...]] | None:
        """Широта, затем долгота. При полярной ошибке дома не подменяются."""
        try:
            cusps, angles = swe.houses(_julian(moment), latitude, longitude, b"P")
        except swe.Error:
            return None
        if len(cusps) < 12 or len(angles) < 1:
            return None
        return float(angles[0]), tuple(float(cusps[index]) for index in range(12))

    def lunar_day(self, moment: datetime, latitude: float, longitude: float) -> int | None:
        target = _julian(moment)
        new_moon = _previous_new_moon(target)
        if new_moon is None:
            return None
        count = 0
        cursor = new_moon
        while count < 31:
            result = swe.rise_trans(
                cursor,
                swe.MOON,
                swe.CALC_RISE,
                (longitude, latitude, 0.0),
                0.0,
                0.0,
                swe.FLG_MOSEPH,
            )
            if result[0] != 0:
                return None
            event = float(result[1][0])
            if event > target:
                break
            count += 1
            cursor = event + 0.01
        if count < 1 or count > 30:
            return None
        return count


def _julian(moment: datetime) -> float:
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    utc = moment.astimezone(UTC)
    hour = utc.hour + utc.minute / 60 + utc.second / 3600 + utc.microsecond / 3_600_000_000
    return float(swe.julday(utc.year, utc.month, utc.day, hour))


def _elongation(julian: float) -> float:
    sun = swe.calc_ut(julian, swe.SUN, _FLAGS)[0][0]
    moon = swe.calc_ut(julian, swe.MOON, _FLAGS)[0][0]
    return float((moon - sun) % 360)


def _previous_new_moon(target: float) -> float | None:
    previous: float | None = None
    cursor = target
    for _step in range(35 * 24):
        current = _elongation(cursor)
        if previous is not None and current > 300 and previous < 60:
            older = cursor
            newer = cursor + 1 / 24
            for _refine in range(40):
                middle = (older + newer) / 2
                if _elongation(middle) < 180:
                    newer = middle
                else:
                    older = middle
            return newer
        previous = current
        cursor -= 1 / 24
    return None
