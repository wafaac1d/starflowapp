"""Местное время уведомления. Слот — каждые 30 минут. Досылка — три часа.

Весенний разрыв: если выбранные часы не существуют, досылка начинается
в первую существующую минуту после разрыва. Осенний повтор часа не создаёт
второе событие: ключ события — календарная дата, а не fold.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CATCHUP = timedelta(hours=3)
LEASE = timedelta(minutes=2)

SLOTS: tuple[str, ...] = tuple(
    f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 30)
)


def parse_slot(value: str) -> time:
    if value not in SLOTS:
        raise ValueError("slot")
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def slot_label(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def known_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("zone") from error


def is_due(moment: datetime, zone_name: str, slot: time, *, catchup: timedelta = CATCHUP) -> bool:
    zone = known_zone(zone_name)
    local = moment.astimezone(zone)
    start = _slot_start(local.date(), slot, zone)
    return start <= local < start + catchup


def local_date(moment: datetime, zone_name: str) -> datetime:
    return moment.astimezone(known_zone(zone_name))


def warm_window(moment: datetime, zone_name: str) -> bool:
    """Прогрев до утренних рассылок: 05:00–08:00 в DEFAULT_TIMEZONE."""
    hour = moment.astimezone(known_zone(zone_name)).hour
    return 5 <= hour < 8


def _slot_start(day: date, slot: time, zone: ZoneInfo) -> datetime:
    wall = datetime.combine(day, slot, tzinfo=zone)
    if _wall_exists(wall):
        return wall
    cursor = wall
    for _step in range(180):
        cursor += timedelta(minutes=1)
        if _wall_exists(cursor):
            return cursor
    return cursor


def _wall_exists(wall: datetime) -> bool:
    back = wall.astimezone(ZoneInfo("UTC")).astimezone(wall.tzinfo)
    return (back.year, back.month, back.day, back.hour, back.minute, back.fold) == (
        wall.year,
        wall.month,
        wall.day,
        wall.hour,
        wall.minute,
        wall.fold,
    )
