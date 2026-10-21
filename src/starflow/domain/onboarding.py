"""Шаги черновика. Клиент не назначает шаг сам."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from starflow.domain.errors import BirthTimeInvalid, FieldInvalid
from starflow.domain.profile import ensure_birth_time

STEPS: tuple[str, ...] = ("welcome", "name", "date", "time", "timezone", "place", "done")


def previous_step(step: str) -> str:
    if step in {"timezone", "place"}:
        return "time"
    index = STEPS.index(step)
    if index <= 0:
        return "welcome"
    return STEPS[index - 1]


def parse_display_name(value: str | None) -> str:
    if value is None:
        raise FieldInvalid("display_name", "errors.name_required")
    cleaned = value.strip()
    if not cleaned:
        raise FieldInvalid("display_name", "errors.name_required")
    if len(cleaned) > 80:
        raise FieldInvalid("display_name", "errors.name_too_long")
    return cleaned


def parse_birth_date(value: str | None, *, today: date | None = None) -> date:
    if value is None:
        raise FieldInvalid("birth_date", "errors.date_invalid")
    parts = value.strip().split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise FieldInvalid("birth_date", "errors.date_invalid")
    day, month, year = (int(part) for part in parts)
    try:
        parsed = date(year, month, day)
    except ValueError as error:
        raise FieldInvalid("birth_date", "errors.date_invalid") from error
    current = date.today() if today is None else today
    if parsed.year < 1900:
        raise FieldInvalid("birth_date", "errors.date_invalid")
    if parsed > current:
        raise FieldInvalid("birth_date", "errors.date_future")
    return parsed


def parse_birth_time(value: str | None, unknown: bool) -> time | None:
    if unknown:
        try:
            ensure_birth_time(None, True)
        except BirthTimeInvalid as error:
            raise FieldInvalid("birth_time", "errors.time_invalid") from error
        return None
    if value is None:
        raise FieldInvalid("birth_time", "errors.time_invalid")
    parts = value.strip().split(":")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise FieldInvalid("birth_time", "errors.time_invalid")
    hour, minute = int(parts[0]), int(parts[1])
    try:
        parsed = time(hour, minute)
    except ValueError as error:
        raise FieldInvalid("birth_time", "errors.time_invalid") from error
    return parsed


def parse_timezone(value: str | None) -> str:
    if value is None or not value.strip():
        raise FieldInvalid("timezone", "errors.timezone_invalid")
    name = value.strip()
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise FieldInvalid("timezone", "errors.timezone_invalid") from error
    return name


def next_after(step: str, *, premium: bool) -> str:
    if step == "welcome":
        return "name"
    if step == "name":
        return "date"
    if step == "date":
        return "time"
    if step == "time":
        return "place" if premium else "done"
    if step == "timezone":
        return "place" if premium else "done"
    if step == "place":
        return "done"
    return "done"


def age_allows(auth_date: float, now: datetime, max_age: int, future_skew: int) -> bool:
    age = now.timestamp() - auth_date
    return -future_skew <= age <= max_age
