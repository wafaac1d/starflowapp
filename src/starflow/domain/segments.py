"""Ключ общего прогноза. В сегмент не входят личные дата, время и место."""

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_SUN = frozenset({"day", "week", "advice"})
_DETAIL = frozenset({"today_detail", "tomorrow"})
_OPEN_PERIOD = {
    "day": "date",
    "advice": "date",
    "moon": "date",
    "today_detail": "date",
    "tomorrow": "date",
    "week": "week",
    "compatibility": "week",
    "personal_day": "date",
    "personal_week": "week",
    "topics": "date",
    "calendar": "month",
    "synastry": "date",
    "natal": "natal",
}


def cacheable(kind: str) -> bool:
    return kind != "assistant" and kind in _OPEN_PERIOD


def forecast_cache_key(
    forecast_type: str,
    period_key: str,
    segment: str,
    topic: str,
    locale: str,
    prompt_version: int,
) -> str:
    return "|".join((forecast_type, period_key, segment, topic, locale, str(prompt_version)))


def period_key(kind: str, moment: datetime, zone_name: str) -> str:
    local = _local(moment, zone_name)
    window = _OPEN_PERIOD[kind]
    if window == "date":
        return local.date().isoformat()
    if window == "week":
        year, week, _day = local.date().isocalendar()
        return f"{year}-W{week:02d}"
    if window == "month":
        return f"{local.year:04d}-{local.month:02d}"
    return "natal"


def expires_at(kind: str, moment: datetime, zone_name: str) -> datetime:
    local = _local(moment, zone_name)
    zone = ZoneInfo(zone_name)
    window = _OPEN_PERIOD[kind]
    if window == "date":
        next_day = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=zone)
        return next_day + timedelta(hours=6)
    if window == "week":
        monday = local.date() - timedelta(days=local.weekday())
        return datetime.combine(monday + timedelta(days=7), time.min, tzinfo=zone)
    if window == "month":
        year = local.year + (1 if local.month == 12 else 0)
        month = 1 if local.month == 12 else local.month + 1
        return datetime.combine(date(year, month, 1), time.min, tzinfo=zone)
    return datetime(9999, 1, 1, tzinfo=UTC)


def sun_segment(sign: str) -> str:
    return sign


def pair_segment(left: str, right: str) -> str:
    ordered = sorted((left, right))
    return f"{ordered[0]}|{ordered[1]}"


def detail_segment(sun: str, moon: str, decan: int) -> str:
    return f"{sun}+{moon}+{decan}"


def personal_segment(sun: str, moon: str | None, ascendant: str | None) -> str:
    return f"{sun}+{moon or 'unknown'}+{ascendant or 'unknown'}"


def moon_segment(day: date) -> str:
    return day.isoformat()


def natal_segment(planet_signs: list[str], house_signs: list[str], aspect_names: list[str]) -> str:
    raw = "|".join((*planet_signs, *house_signs, *aspect_names))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def synastry_segment(left: dict[str, str | None], right: dict[str, str | None]) -> str:
    ordered = sorted((_profile_token(left), _profile_token(right)))
    return f"{ordered[0]}|{ordered[1]}"


def calendar_segment(sun: str, moon: str, ascendant: str | None, month: str) -> str:
    return f"{sun}+{moon}+{ascendant or 'unknown'}+{month}"


def representative_facts(kind: str, segment: str) -> dict[str, object]:
    if kind in _SUN:
        return {"sun": segment}
    if kind in {"personal_day", "personal_week", "topics"}:
        sun, moon, ascendant = segment.split("+")
        return {"sun": sun, "moon": moon, "ascendant": ascendant}
    if kind in _DETAIL:
        sun, moon, decan = segment.split("+")
        return {"sun": sun, "moon": moon, "decan": int(decan)}
    if kind == "compatibility":
        left, right = segment.split("|")
        return {"signs": [left, right]}
    if kind == "moon":
        return {"date": segment}
    if kind == "calendar":
        sun, moon, ascendant, month = segment.split("+")
        return {"sun": sun, "moon": moon, "ascendant": ascendant, "month": month}
    return {"segment": segment}


def facts_text(facts: dict[str, object]) -> str:
    return json.dumps(facts, ensure_ascii=False, sort_keys=True)


def _profile_token(profile: dict[str, str | None]) -> str:
    sun = profile.get("sun") or "unknown"
    moon = profile.get("moon") or "unknown"
    ascendant = profile.get("asc") or "unknown"
    return f"{sun}:{moon}:{ascendant}"


def _local(moment: datetime, zone_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    return moment.astimezone(ZoneInfo(zone_name))
