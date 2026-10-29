"""Проверка дней, которые модель назвала благоприятными. Чужой месяц не принимается."""

import calendar
import re
from dataclasses import dataclass

from starflow.ai.guard import plain_text
from starflow.domain.calendar_reading import parse_month
from starflow.domain.errors import FieldInvalid
from starflow.domain.stars import subject_ok
from starflow.i18n.guard import contains_emoji

PRESETS = {
    "meeting": "Встреча",
    "trip": "Поездка",
    "purchase": "Покупка",
}
CUSTOM = "custom"
_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_NOTE_LIMIT = 240


@dataclass(frozen=True)
class FavorableDay:
    date: str
    start: str
    end: str
    note: str


def event_label(event: str, custom: str) -> str:
    if event == CUSTOM:
        cleaned = plain_text(custom)
        if len(cleaned) < 2 or len(cleaned) > 40:
            raise FieldInvalid("custom", "errors.validation")
        return cleaned
    label = PRESETS.get(event)
    if label is None:
        raise FieldInvalid("event", "errors.validation")
    return label


def favorable_subject(month: str, event: str, custom: str) -> str:
    try:
        parse_month(month)
    except ValueError as error:
        raise FieldInvalid("month", "errors.validation") from error
    label = event_label(event, custom)
    slug = "-".join(
        part
        for part in (
            "".join(character if character.isalnum() else "-" for character in label.casefold())
        ).split("-")
        if part
    )
    subject = f"{month}:{event}:{slug}"
    if slug == "" or not subject_ok(subject):
        raise FieldInvalid("event", "errors.validation")
    return subject


def nearest_favorable(days: tuple[FavorableDay, ...], today: str) -> tuple[FavorableDay, ...]:
    if not days:
        return ()
    upcoming = tuple(day for day in days if day.date >= today)
    if upcoming:
        return (upcoming[0],)
    return (days[-1],)


def accept_favorable(year: int, month: int, payload: object) -> tuple[FavorableDay, ...] | None:
    if not isinstance(payload, dict):
        return None
    raw_days = payload.get("days")
    if not isinstance(raw_days, list):
        return None
    last = calendar.monthrange(year, month)[1]
    prefix = f"{year:04d}-{month:02d}-"
    found: dict[str, FavorableDay] = {}
    for item in raw_days:
        day = _day(item, prefix, last)
        if day is None or day.date in found:
            continue
        found[day.date] = day
        if len(found) == 8:
            break
    if not found:
        return None
    return tuple(found[key] for key in sorted(found))


def _day(item: object, prefix: str, last: int) -> FavorableDay | None:
    if not isinstance(item, dict):
        return None
    raw_date = item.get("date")
    start = item.get("start")
    end = item.get("end")
    note = item.get("note")
    if not isinstance(raw_date, str) or not raw_date.startswith(prefix):
        return None
    tail = raw_date.removeprefix(prefix)
    if len(tail) != 2 or not tail.isdigit() or not 1 <= int(tail) <= last:
        return None
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    if _CLOCK.fullmatch(start) is None or _CLOCK.fullmatch(end) is None or start >= end:
        return None
    if not isinstance(note, str):
        return None
    cleaned = plain_text(note)
    if cleaned == "" or len(cleaned) > _NOTE_LIMIT or contains_emoji(cleaned):
        return None
    return FavorableDay(raw_date, start, end, cleaned)
