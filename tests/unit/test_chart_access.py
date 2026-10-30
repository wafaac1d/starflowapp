"""Границы знаков, местное время, карта без выдуманных углов и геокодер."""

import asyncio
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from starflow.astro.ecliptic import sign_for_longitude
from starflow.astro.swiss import SwissEphemeris
from starflow.domain.astrology import facts_for_longitude, moon_near_cusp
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.entitlement import Grant, access_end, grant_is_open
from starflow.domain.local_time import LocalWhen, classify_local, user_week
from starflow.domain.plans import load_plans
from starflow.domain.quota import PremiumRequired
from starflow.domain.records import PlaceHit, Profile
from starflow.services.chart import ChartService
from starflow.services.nominatim import NominatimLookup, format_short_place
from starflow.services.places import PlaceService, RequestPace
from starflow.services.timezones import FinderTimezone

ROOT = Path(__file__).resolve().parents[2]

_BOUNDARIES = (
    (date(1990, 1, 19), "козерог"),
    (date(1990, 1, 20), "водолей"),
    (date(1990, 2, 18), "водолей"),
    (date(1990, 2, 19), "рыбы"),
    (date(1990, 3, 20), "рыбы"),
    (date(1990, 3, 21), "овен"),
    (date(1990, 4, 19), "овен"),
    (date(1990, 4, 20), "телец"),
    (date(1990, 5, 20), "телец"),
    (date(1990, 5, 21), "близнецы"),
    (date(1990, 6, 20), "близнецы"),
    (date(1990, 6, 21), "рак"),
    (date(1990, 7, 22), "рак"),
    (date(1990, 7, 23), "лев"),
    (date(1990, 8, 22), "лев"),
    (date(1990, 8, 23), "дева"),
    (date(1990, 9, 22), "дева"),
    (date(1990, 9, 23), "весы"),
    (date(1990, 10, 22), "весы"),
    (date(1990, 10, 23), "скорпион"),
    (date(1990, 11, 21), "скорпион"),
    (date(1990, 11, 22), "стрелец"),
    (date(1990, 12, 21), "стрелец"),
    (date(1990, 12, 22), "козерог"),
    (date(1990, 1, 2), "козерог"),
)


class _Ephemeris:
    def __init__(self) -> None:
        self.houses_calls = 0
        self.position_calls = 0

    def positions(self, moment: datetime) -> tuple[object, ...]:
        self.position_calls += 1
        from starflow.astro.swiss import BodyPosition

        return (
            BodyPosition("солнце", 10.0, 1.0),
            BodyPosition("луна", 40.0, 12.0),
            BodyPosition("марс", 100.0, -0.2),
        )

    def houses(
        self,
        moment: datetime,
        latitude: float,
        longitude: float,
    ) -> tuple[float, tuple[float, ...]]:
        self.houses_calls += 1
        return 15.0, tuple(float(index * 30) for index in range(12))

    def lunar_day(self, moment: datetime, latitude: float, longitude: float) -> int:
        return 7


class _Quota:
    def __init__(self, allowed: bool) -> None:
        self._allowed = allowed

    async def preview(self, user_id: object, feature: str) -> object:
        from starflow.domain.quota import Allowed

        if self._allowed:
            return Allowed()
        return PremiumRequired()


class _Sky:
    def __init__(self) -> None:
        self.calls = 0

    async def for_date(self, day: date) -> dict[str, object]:
        self.calls += 1
        return {"bodies": [{"name": "солнце", "longitude": 280.0}]}


class _Cache:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    async def get(self, key: str) -> dict[str, object] | None:
        return self.rows.get(key)

    async def delete_kind(self, user_id: object, kind: str) -> None:
        self.rows.clear()

    async def put(
        self,
        key: str,
        user_id: object,
        kind: str,
        payload: dict[str, object],
        valid_until: datetime,
    ) -> None:
        self.rows[key] = payload


class _Profiles:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    async def ensure(self, user_id: object) -> Profile:
        return self.profile


class _Work:
    def __init__(self, profile: Profile) -> None:
        self.profiles = _Profiles(profile)
        self.forecast_cache = _Cache()

    async def __aenter__(self) -> "_Work":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None


def _profile(**overrides: object) -> Profile:
    values: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "display_name": "мария",
        "birth_date": date(1990, 1, 2),
        "birth_time": None,
        "birth_time_unknown": True,
        "birth_place": None,
        "latitude": None,
        "longitude": None,
        "timezone": "Europe/Moscow",
        "onboarding_step": "done",
    }
    values.update(overrides)
    return Profile(**values)  # type: ignore[arg-type]


def _service(profile: Profile, allowed: bool = True) -> tuple[ChartService, _Ephemeris, _Sky]:
    ephemeris = _Ephemeris()
    sky = _Sky()
    work = _Work(profile)
    service = ChartService(lambda: work, ephemeris, _Quota(allowed), sky)
    return service, ephemeris, sky


def test_calendar_boundaries_and_decans() -> None:
    for day, name in _BOUNDARIES:
        assert calendar_sign(day) == name
    aries = facts_for_longitude(0)
    assert aries.sign == "овен"
    assert aries.decan == 1
    assert aries.decan_ruler == "марс"
    assert aries.element == "огонь"
    assert aries.modality == "кардинальный"
    assert facts_for_longitude(10).decan == 2
    assert facts_for_longitude(10).decan_ruler == "солнце"
    assert facts_for_longitude(20).decan == 3
    assert facts_for_longitude(29.9).decan == 3
    taurus = facts_for_longitude(30)
    assert taurus.sign == "телец"
    assert taurus.decan == 1
    assert taurus.decan_ruler == "меркурий"
    assert sign_for_longitude(359.9) == "рыбы"
    assert sign_for_longitude(-1) == "рыбы"
    assert moon_near_cusp(1)
    assert not moon_near_cusp(15)


def test_local_time_keeps_gap_and_fold_apart() -> None:
    assert classify_local(date(2026, 3, 29), clock(2, 30), "Europe/Berlin") is LocalWhen.GAP
    assert classify_local(date(2026, 10, 25), clock(2, 30), "Europe/Berlin") is LocalWhen.AMBIGUOUS
    assert classify_local(date(2026, 6, 1), clock(12, 0), "Europe/Berlin") is LocalWhen.UNIQUE
    moment = datetime(2026, 10, 21, 12, tzinfo=UTC)
    start, end = user_week(moment, "Europe/Moscow")
    assert start == datetime(2026, 10, 19, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    assert end - start == timedelta(days=7)


def test_plans_keep_feature_limits_together() -> None:
    plans = load_plans(ROOT / "resources" / "plans.yaml", price_stars=250)
    assert plans.free.favorites_limit == 3
    assert plans.premium.grace_hours == 1
    assert plans.premium.reminder_days == 3
    assert plans.trial.once is True
    assert plans.gift.days == 30
    assert plans.rule("favorite").limit == 3
    assert plans.rule("assistant").limit == 20
    assert plans.rule("assistant").window == "paid_period"
    assert plans.rule("compatibility").window == "user_week"
    assert plans.rule("natal").gate == "premium"


def test_independent_grants_and_subscription_grace() -> None:
    now = datetime(2026, 6, 15, tzinfo=UTC)
    payment = _grant("payment", now - timedelta(days=1), now + timedelta(days=10))
    assert access_end((payment,), now) is None
    gift = _grant("gift", now - timedelta(days=1), now + timedelta(days=5))
    subscription = _grant(
        "subscription",
        now - timedelta(days=30),
        now - timedelta(days=1),
        grace_until=now + timedelta(days=2),
    )
    assert access_end((subscription,), now) == subscription.grace_until
    assert access_end((subscription, gift), now) == gift.period_end
    revoked = _grant(
        "subscription",
        now - timedelta(days=1),
        now + timedelta(days=20),
        revoked_at=now,
    )
    assert access_end((revoked, gift), now) == gift.period_end
    trial = _grant(
        "trial",
        now - timedelta(days=10),
        now - timedelta(days=1),
        grace_until=now + timedelta(days=3),
    )
    assert not grant_is_open(trial, now)


def _grant(
    source: str,
    start: datetime,
    end: datetime,
    *,
    grace_until: datetime | None = None,
    revoked_at: datetime | None = None,
) -> Grant:
    return Grant(
        id=uuid4(),
        user_id=uuid4(),
        source=source,
        status="revoked" if revoked_at is not None else "active",
        period_start=start,
        period_end=end,
        grace_until=grace_until,
        revoked_at=revoked_at,
    )


@pytest.mark.asyncio
async def test_unknown_time_does_not_invent_angles() -> None:
    service, ephemeris, sky = _service(_profile())
    view = await service.read(uuid4())
    assert view.sun_sign == "козерог"
    assert view.sun_sign_source == "calendar"
    assert view.moon_sign is None
    assert view.ascendant_sign is None
    assert view.houses is None
    assert "time_unknown" in view.limitations
    assert ephemeris.houses_calls == 0
    assert ephemeris.position_calls == 1
    assert sky.calls == 0


@pytest.mark.asyncio
async def test_gap_and_fold_keep_the_calendar_sign() -> None:
    gap = _profile(
        birth_date=date(2026, 3, 29),
        birth_time=clock(2, 30),
        birth_time_unknown=False,
        birth_place="берлин",
        latitude=Decimal("52.520000"),
        longitude=Decimal("13.405000"),
        timezone="Europe/Berlin",
    )
    service, ephemeris, _sky = _service(gap)
    view = await service.read(gap.user_id)
    assert "local_time_gap" in view.limitations
    assert view.sun_sign_source == "calendar"
    assert view.houses is None
    assert ephemeris.position_calls == 0
    fold = _profile(
        birth_date=date(2026, 10, 25),
        birth_time=clock(2, 30),
        birth_time_unknown=False,
        birth_place="берлин",
        latitude=Decimal("52.520000"),
        longitude=Decimal("13.405000"),
        timezone="Europe/Berlin",
    )
    service, ephemeris, _sky = _service(fold)
    view = await service.read(fold.user_id)
    assert "local_time_ambiguous" in view.limitations
    assert view.moon_sign is None
    assert ephemeris.houses_calls == 0


@pytest.mark.asyncio
async def test_full_chart_uses_ephemeris_and_paywall_hides_angles() -> None:
    profile = _profile(
        birth_time=clock(12, 0),
        birth_time_unknown=False,
        birth_place="москва",
        latitude=Decimal("55.750000"),
        longitude=Decimal("37.620000"),
    )
    service, ephemeris, sky = _service(profile, allowed=False)
    view = await service.read(profile.user_id)
    assert view.sun_sign == "овен"
    assert view.sun_sign_source == "ephemeris"
    assert view.moon_sign is None
    assert view.houses is None
    assert view.natal_access == "premium_required"
    assert ephemeris.houses_calls == 0
    assert sky.calls == 0
    service, ephemeris, sky = _service(profile, allowed=True)
    view = await service.read(profile.user_id)
    again = await service.read(profile.user_id)
    assert view.moon_sign == "телец"
    assert view.ascendant_sign == "овен"
    assert view.houses is not None
    assert len(view.houses) == 12
    assert view.house_cusps == tuple(float(index * 30) for index in range(12))
    assert again.house_cusps == view.house_cusps
    assert again.moon_sign == view.moon_sign
    assert ephemeris.houses_calls == 1
    assert sky.calls == 2


def test_moshier_epoch_is_reproducible() -> None:
    swiss = SwissEphemeris()
    moment = datetime(2000, 1, 1, 12, tzinfo=UTC)
    sun = next(body for body in swiss.positions(moment) if body.name == "солнце")
    assert abs(sun.longitude - 280.36891967534325) < 0.02
    assert sign_for_longitude(sun.longitude) == "козерог"
    houses = swiss.houses(moment, 55.75, 37.62)
    assert houses is not None
    assert abs(houses[0] - 87.78110276529328) < 0.02
    assert swiss.lunar_day(moment, 55.75, 37.62) == 24


def test_nominatim_agent_and_timezone_lookup() -> None:
    lookup = NominatimLookup("https://nominatim.openstreetmap.org", "StarFlow/0.1")
    assert lookup._user_agent == "StarFlow/0.1"
    assert FinderTimezone().zone(55.75, 37.62) == "Europe/Moscow"


def test_format_short_place() -> None:
    assert (
        format_short_place(
            "Москва, Центральный административный округ, Москва, 101000, Россия",
            {"address": {"country": "Россия", "city": "Москва"}},
        )
        == "Россия, Москва"
    )
    assert (
        format_short_place(
            "Москва, Центральный административный округ, Москва, 101000, Россия"
        )
        == "Россия, Москва"
    )
    assert (
        format_short_place("Санкт-Петербург, Северо-Западный федеральный округ, Россия")
        == "Россия, Санкт-Петербург"
    )
    assert format_short_place("Minsk, Belarus") == "Minsk, Belarus"
    assert format_short_place("Париж") == "Париж"


class _Lookup:
    def __init__(self, delay: float = 0) -> None:
        self.delay = delay
        self.calls = 0
        self.current = 0
        self.maximum = 0

    async def search(self, query: str) -> list[PlaceHit]:
        self.current += 1
        self.maximum = max(self.maximum, self.current)
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        self.current -= 1
        return [PlaceHit(query, Decimal("55.750000"), Decimal("37.620000"))]


class _Geo:
    def __init__(self) -> None:
        self.saved: dict[str, list[PlaceHit]] = {}

    async def get_results(self, query: str) -> list[PlaceHit] | None:
        return self.saved.get(query)

    async def store_results(self, query: str, hits: list[PlaceHit]) -> None:
        self.saved[query] = list(hits)


class _Subs:
    async def has_active(self, user_id: object, now: datetime) -> bool:
        return True


class _PlaceWork:
    def __init__(self, geo: _Geo) -> None:
        self.geocodes = geo
        self.subscriptions = _Subs()

    async def __aenter__(self) -> "_PlaceWork":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_geocoder_uses_cache_pace_and_a_single_flight() -> None:
    geo = _Geo()
    lookup = _Lookup()
    service = PlaceService(
        lambda: _PlaceWork(geo),
        lookup,
        RequestPace(0.05),
        user_gap_sec=0,
    )
    user_id = uuid4()
    await service.search(user_id, "москва")
    await service.search(user_id, "москва")
    assert lookup.calls == 1
    other = _Lookup()
    paced = PlaceService(lambda: _PlaceWork(_Geo()), other, RequestPace(0.05), user_gap_sec=0)
    started = time.monotonic()
    await paced.search(user_id, "казань")
    await paced.search(user_id, "тула")
    assert time.monotonic() - started >= 0.05
    slow = _Lookup(delay=0.05)
    guarded = PlaceService(lambda: _PlaceWork(_Geo()), slow, RequestPace(0), user_gap_sec=0)
    await asyncio.gather(guarded.search(user_id, "омск"), guarded.search(user_id, "пермь"))
    assert slow.maximum == 1
    gapped = _Lookup()
    spaced = PlaceService(lambda: _PlaceWork(_Geo()), gapped, RequestPace(0), user_gap_sec=0.15)
    started = time.monotonic()
    await spaced.search(user_id, "сочи")
    await spaced.search(user_id, "уфа")
    assert time.monotonic() - started >= 0.15
