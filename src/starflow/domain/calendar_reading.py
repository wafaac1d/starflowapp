"""Проверка JSON астрокалендаря. Неполный или чужой месяц не считается текстом."""

import calendar
from dataclasses import dataclass
from datetime import datetime

from starflow.ai.guard import plain_text
from starflow.domain.features import TOPICS
from starflow.i18n.guard import contains_emoji

_SCORE_MIN = 1
_SCORE_MAX = 5


@dataclass(frozen=True)
class DayMark:
    day: str
    scores: tuple[tuple[str, int], ...]
    note: str


def parse_month(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as error:
        raise ValueError("month") from error
    return parsed.year, parsed.month


def accept_calendar(
    year: int, month: int, payload: object
) -> tuple[str, tuple[DayMark, ...]] | None:
    if not isinstance(payload, dict):
        return None
    title = payload.get("title")
    raw_days = payload.get("days")
    if not isinstance(title, str) or not isinstance(raw_days, list):
        return None
    clean_title = plain_text(title)
    if clean_title == "" or contains_emoji(clean_title):
        return None
    expected = _dates(year, month)
    found: dict[str, DayMark] = {}
    for item in raw_days:
        mark = _day(item, expected)
        if mark is None or mark.day in found:
            return None
        found[mark.day] = mark
    if set(found) != expected:
        return None
    ordered = tuple(found[day] for day in sorted(expected))
    return clean_title, ordered


def _dates(year: int, month: int) -> set[str]:
    count = calendar.monthrange(year, month)[1]
    return {f"{year:04d}-{month:02d}-{day:02d}" for day in range(1, count + 1)}


def _day(item: object, expected: set[str]) -> DayMark | None:
    if not isinstance(item, dict):
        return None
    day = item.get("date")
    scores = item.get("scores")
    note = item.get("note")
    if not isinstance(day, str) or day not in expected or not isinstance(scores, dict):
        return None
    if not isinstance(note, str):
        return None
    clean_note = plain_text(note)
    if clean_note == "" or contains_emoji(clean_note):
        return None
    parsed: list[tuple[str, int]] = []
    if set(scores) != set(TOPICS):
        return None
    for theme in TOPICS:
        score = scores.get(theme)
        if isinstance(score, bool) or not isinstance(score, int):
            return None
        if score < _SCORE_MIN or score > _SCORE_MAX:
            return None
        parsed.append((theme, score))
    return DayMark(day, tuple(parsed), clean_note)
