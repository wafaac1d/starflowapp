"""Проверка дней, которые модель назвала благоприятными. Чужой месяц не принимается."""

import calendar
import re
from dataclasses import dataclass

from starflow.ai.guard import guarded_copy, plain_text
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
_WORD = re.compile(r"[A-Za-zА-Яа-яЁё]{2,}")
_REPEAT = re.compile(r"(.)\1{3,}")
_VOWELS = frozenset("аеёиоуыэюяaeiouy")
_JUNK = frozenset(
    {
        "тест",
        "test",
        "asdf",
        "asdfgh",
        "qwe",
        "qwert",
        "qwerty",
        "zxc",
        "zxcv",
        "йцук",
        "йцукен",
        "фыва",
        "хз",
        "лол",
        "lol",
        "кек",
        "ок",
        "ok",
        "нет",
        "да",
        "ерунда",
        "хрень",
        "привет",
        "ааа",
        "аааа",
    }
)


@dataclass(frozen=True)
class FavorableDay:
    date: str
    start: str
    end: str
    note: str


def clean_custom_event(raw: str) -> str:
    cleaned = plain_text(raw)
    folded = cleaned.casefold()
    letters = [character for character in folded if character.isalpha()]
    compact = folded.replace(" ", "")
    words = _WORD.findall(cleaned)
    readable = any(len(word) >= 3 for word in words) or len(words) >= 2
    if (
        len(cleaned) < 2
        or len(cleaned) > 40
        or contains_emoji(cleaned)
        or folded in _JUNK
        or "http" in folded
        or "www." in folded
        or "игнор" in folded
        or len(letters) < 3
        or len(letters) * 2 < len(compact)
        or _REPEAT.search(folded) is not None
        or not any(character in _VOWELS for character in folded)
        or not readable
    ):
        raise FieldInvalid("custom", "errors.validation")
    return cleaned


def event_label(event: str, custom: str) -> str:
    if event == CUSTOM:
        return clean_custom_event(custom)
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


def accept_day_detail(payload: object) -> tuple[str, str, str] | None:
    if not isinstance(payload, dict):
        return None
    title = payload.get("title")
    body = payload.get("body")
    advice = payload.get("advice")
    if not isinstance(title, str) or not isinstance(body, str) or not isinstance(advice, str):
        return None
    guarded = guarded_copy(title, body)
    cleaned_advice = plain_text(advice)
    if (
        guarded is None
        or cleaned_advice == ""
        or contains_emoji(cleaned_advice)
        or len(cleaned_advice) > 400
        or len(guarded[1]) > 1200
    ):
        return None
    return guarded[0], guarded[1], cleaned_advice


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
