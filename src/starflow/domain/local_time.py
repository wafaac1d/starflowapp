"""Местное время рождения. Пропуск и перекрытие перевода часов не выбираются наугад."""

from datetime import UTC, date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class LocalWhen(Enum):
    UNIQUE = "unique"
    AMBIGUOUS = "ambiguous"
    GAP = "gap"


def classify_local(day: date, clock: time, zone_name: str) -> LocalWhen:
    zone = ZoneInfo(zone_name)
    naive = datetime.combine(day, clock)
    earlier = naive.replace(tzinfo=zone, fold=0)
    later = naive.replace(tzinfo=zone, fold=1)
    if earlier.utcoffset() == later.utcoffset():
        return LocalWhen.UNIQUE
    restored = earlier.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if restored != naive:
        return LocalWhen.GAP
    return LocalWhen.AMBIGUOUS


def to_utc(day: date, clock: time, zone_name: str) -> datetime | None:
    if classify_local(day, clock, zone_name) is not LocalWhen.UNIQUE:
        return None
    zone = ZoneInfo(zone_name)
    return datetime.combine(day, clock).replace(tzinfo=zone).astimezone(UTC)


def user_week(moment: datetime, zone_name: str) -> tuple[datetime, datetime]:
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    zone = ZoneInfo(zone_name)
    local = moment.astimezone(zone)
    monday = local.date() - timedelta(days=local.weekday())
    start = datetime.combine(monday, time.min, tzinfo=zone)
    return start, start + timedelta(days=7)
