"""Натальная карта. Углы и точная луна не выдумываются без времени и места."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.astro.ecliptic import sign_for_longitude
from starflow.astro.swiss import BodyPosition
from starflow.domain.astrology import (
    AspectHit,
    aspects_between,
    facts_for_longitude,
    phase_name,
    transit_aspects,
)
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import Conflict
from starflow.domain.features import cache_key
from starflow.domain.local_time import LocalWhen, classify_local, to_utc
from starflow.domain.quota import Allowed, QuotaDecision
from starflow.domain.records import Profile
from starflow.domain.time import local_date, now_utc
from starflow.repositories.sql import ForecastCacheRepository, ProfileRepository

_BLOCKING = frozenset(
    {
        "time_unknown",
        "place_missing",
        "local_time_ambiguous",
        "local_time_gap",
        "timezone_missing",
        "birth_date_missing",
    }
)


@dataclass(frozen=True)
class PlanetPlacement:
    name: str
    longitude: float
    sign: str | None
    element: str | None
    modality: str | None
    ruler: str | None
    decan: int | None
    decan_ruler: str | None
    retrograde: bool
    exact: bool


@dataclass(frozen=True)
class ChartView:
    sun_sign: str | None
    sun_sign_source: str
    moon_sign: str | None
    ascendant_sign: str | None
    houses: tuple[str, ...] | None
    planets: tuple[PlanetPlacement, ...]
    aspects: tuple[str, ...]
    transits: tuple[str, ...]
    lunar_day: int | None
    phase_name: str | None
    limitations: tuple[str, ...]
    natal_access: str
    house_cusps: tuple[float, ...] | None


class Ephemeris(Protocol):
    def positions(self, moment: datetime) -> tuple[BodyPosition, ...]: ...

    def houses(
        self,
        moment: datetime,
        latitude: float,
        longitude: float,
    ) -> tuple[float, tuple[float, ...]] | None: ...

    def lunar_day(self, moment: datetime, latitude: float, longitude: float) -> int | None: ...


class AccessPreview(Protocol):
    async def preview(self, user_id: UUID, feature: str) -> QuotaDecision: ...


class DaySky(Protocol):
    async def for_date(self, day: date) -> dict[str, object]: ...


class ChartStore(Protocol):
    profiles: ProfileRepository
    forecast_cache: ForecastCacheRepository

    async def commit(self) -> None: ...


class ChartWork(Protocol):
    async def __aenter__(self) -> ChartStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class ChartService:
    def __init__(
        self,
        uow_factory: Callable[[], ChartWork],
        ephemeris: Ephemeris,
        quota: AccessPreview,
        sky: DaySky,
    ) -> None:
        self._uow_factory = uow_factory
        self._ephemeris = ephemeris
        self._quota = quota
        self._sky = sky

    async def read(self, user_id: UUID) -> ChartView:
        decision = await self._quota.preview(user_id, "natal")
        access = "allowed" if isinstance(decision, Allowed) else "premium_required"
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
        fingerprint = _fingerprint(profile, access)
        key = cache_key("natal", str(user_id), fingerprint)
        async with self._uow_factory() as uow:
            cached = await uow.forecast_cache.get(key)
        view = None if cached is None else _from_payload(cached)
        if view is not None and view.houses is not None and view.house_cusps is None:
            view = None
        if view is None:
            view = self._calculate(profile, access)
            await self._store(user_id, key, view)
        if _angles(view):
            sky = await self._sky.for_date(_content_date(profile))
            view = replace(view, transits=_transits(view, sky))
        return view

    def _calculate(self, profile: Profile, access: str) -> ChartView:
        limitations = _limitations(profile)
        moment = _moment(profile, limitations)
        positions = () if moment is None else self._ephemeris.positions(moment)
        sun_sign, source = _sun(profile, positions, limitations)
        exact = _BLOCKING.isdisjoint(limitations)
        angles = access == "allowed" and exact
        planets = _planets(positions, source, include_moon=angles)
        phase = _phase(positions) if positions else None
        ascendant: str | None = None
        houses: tuple[str, ...] | None = None
        house_cusps: tuple[float, ...] | None = None
        lunar_day: int | None = None
        aspects: tuple[str, ...] = ()
        latitude_value = profile.latitude
        longitude_value = profile.longitude
        if (
            angles
            and moment is not None
            and latitude_value is not None
            and longitude_value is not None
        ):
            latitude = float(latitude_value)
            longitude = float(longitude_value)
            found = self._ephemeris.houses(moment, latitude, longitude)
            if found is None:
                limitations = (*limitations, "houses_unavailable")
            else:
                ascendant_longitude, cusps = found
                ascendant = sign_for_longitude(ascendant_longitude)
                house_cusps = tuple(float(cusp) for cusp in cusps)
                houses = tuple(sign_for_longitude(cusp) for cusp in house_cusps)
            lunar_day = self._ephemeris.lunar_day(moment, latitude, longitude)
            aspects = tuple(_aspect_text(hit) for hit in aspects_between(_longitudes(positions)))
        moon = next((item.sign for item in planets if item.name == "луна"), None)
        return ChartView(
            sun_sign=sun_sign,
            sun_sign_source=source,
            moon_sign=moon,
            ascendant_sign=ascendant,
            houses=houses,
            planets=planets,
            aspects=aspects,
            transits=(),
            lunar_day=lunar_day,
            phase_name=phase,
            limitations=tuple(limitations),
            natal_access=access,
            house_cusps=house_cusps,
        )

    async def _store(self, user_id: UUID, key: str, view: ChartView) -> None:
        payload = _payload(view)
        try:
            async with self._uow_factory() as uow:
                await uow.forecast_cache.delete_kind(user_id, "natal")
                await uow.forecast_cache.put(
                    key,
                    user_id,
                    "natal",
                    payload,
                    now_utc() + timedelta(days=366),
                )
                await uow.commit()
        except Conflict:
            return


def _angles(view: ChartView) -> bool:
    return view.natal_access == "allowed" and _BLOCKING.isdisjoint(view.limitations)


def _fingerprint(profile: Profile, access: str) -> str:
    return "|".join(
        (
            "" if profile.birth_date is None else profile.birth_date.isoformat(),
            "" if profile.birth_time is None else profile.birth_time.isoformat(),
            "unknown" if profile.birth_time_unknown else "known",
            "" if profile.latitude is None else str(profile.latitude),
            "" if profile.longitude is None else str(profile.longitude),
            profile.timezone or "",
            access,
        )
    )


def _content_date(profile: Profile) -> date:
    if profile.timezone is None:
        return now_utc().date()
    return local_date(now_utc(), profile.timezone)


def _limitations(profile: Profile) -> tuple[str, ...]:
    found: list[str] = []
    if profile.birth_date is None:
        found.append("birth_date_missing")
    if profile.timezone is None:
        found.append("timezone_missing")
        return tuple(found)
    if profile.birth_date is None:
        return tuple(found)
    if profile.birth_time_unknown or profile.birth_time is None:
        found.append("time_unknown")
    else:
        kind = classify_local(profile.birth_date, profile.birth_time, profile.timezone)
        if kind is LocalWhen.GAP:
            found.append("local_time_gap")
        elif kind is LocalWhen.AMBIGUOUS:
            found.append("local_time_ambiguous")
    if profile.latitude is None or profile.longitude is None or not profile.birth_place:
        found.append("place_missing")
    return tuple(found)


def _moment(profile: Profile, limitations: tuple[str, ...]) -> datetime | None:
    if profile.birth_date is None or profile.timezone is None:
        return None
    if "local_time_gap" in limitations or "local_time_ambiguous" in limitations:
        return None
    if "time_unknown" in limitations:
        return to_utc(profile.birth_date, time(12, 0), profile.timezone)
    if profile.birth_time is None:
        return None
    return to_utc(profile.birth_date, profile.birth_time, profile.timezone)


def _sun(
    profile: Profile,
    positions: tuple[BodyPosition, ...],
    limitations: tuple[str, ...],
) -> tuple[str | None, str]:
    if profile.birth_date is None:
        return None, "missing"
    if _BLOCKING.isdisjoint(limitations):
        sun = next(body for body in positions if body.name == "солнце")
        return facts_for_longitude(sun.longitude).sign, "ephemeris"
    return calendar_sign(profile.birth_date), "calendar"


def _planets(
    positions: tuple[BodyPosition, ...],
    source: str,
    *,
    include_moon: bool,
) -> tuple[PlanetPlacement, ...]:
    listed: list[PlanetPlacement] = []
    for body in positions:
        if body.name == "луна" and not include_moon:
            continue
        if body.name == "солнце" and source != "ephemeris":
            continue
        listed.append(_placement(body))
    return tuple(listed)


def _placement(body: BodyPosition) -> PlanetPlacement:
    facts = facts_for_longitude(body.longitude)
    return PlanetPlacement(
        name=body.name,
        longitude=body.longitude,
        sign=facts.sign,
        element=facts.element,
        modality=facts.modality,
        ruler=facts.ruler,
        decan=facts.decan,
        decan_ruler=facts.decan_ruler,
        retrograde=body.retrograde,
        exact=True,
    )


def _phase(positions: tuple[BodyPosition, ...]) -> str | None:
    by_name = {body.name: body.longitude for body in positions}
    sun = by_name.get("солнце")
    moon = by_name.get("луна")
    if sun is None or moon is None:
        return None
    return phase_name(sun, moon)


def _longitudes(positions: tuple[BodyPosition, ...]) -> dict[str, float]:
    return {body.name: body.longitude for body in positions}


def _aspect_text(hit: AspectHit) -> str:
    return f"{hit.first} {hit.name} {hit.second}"


def _transits(view: ChartView, sky: dict[str, object]) -> tuple[str, ...]:
    natal = {f"натал {item.name}": item.longitude for item in view.planets}
    sky_bodies = sky.get("bodies")
    if not isinstance(sky_bodies, list):
        return ()
    transit: dict[str, float] = {}
    for item in sky_bodies:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        longitude = item.get("longitude")
        if isinstance(name, str) and isinstance(longitude, int | float):
            transit[f"небо {name}"] = float(longitude)
    return tuple(f"{hit.second} {hit.name} {hit.first}" for hit in transit_aspects(natal, transit))


def _payload(view: ChartView) -> dict[str, object]:
    return {
        "sun_sign": view.sun_sign,
        "sun_sign_source": view.sun_sign_source,
        "moon_sign": view.moon_sign,
        "ascendant_sign": view.ascendant_sign,
        "houses": None if view.houses is None else list(view.houses),
        "house_cusps": None if view.house_cusps is None else list(view.house_cusps),
        "planets": [
            {
                "name": item.name,
                "longitude": item.longitude,
                "sign": item.sign,
                "element": item.element,
                "modality": item.modality,
                "ruler": item.ruler,
                "decan": item.decan,
                "decan_ruler": item.decan_ruler,
                "retrograde": item.retrograde,
                "exact": item.exact,
            }
            for item in view.planets
        ],
        "aspects": list(view.aspects),
        "lunar_day": view.lunar_day,
        "phase_name": view.phase_name,
        "limitations": list(view.limitations),
        "natal_access": view.natal_access,
    }


def _from_payload(payload: dict[str, object]) -> ChartView | None:
    try:
        return ChartView(
            sun_sign=_optional_text(payload.get("sun_sign")),
            sun_sign_source=_text(payload.get("sun_sign_source")),
            moon_sign=_optional_text(payload.get("moon_sign")),
            ascendant_sign=_optional_text(payload.get("ascendant_sign")),
            houses=_texts(payload.get("houses")),
            planets=_planets_payload(payload.get("planets")),
            aspects=_text_tuple(payload.get("aspects")),
            transits=(),
            lunar_day=_optional_int(payload.get("lunar_day")),
            phase_name=_optional_text(payload.get("phase_name")),
            limitations=_text_tuple(payload.get("limitations")),
            natal_access=_text(payload.get("natal_access")),
            house_cusps=_cusps(payload.get("house_cusps")),
        )
    except (TypeError, ValueError):
        return None


def _planets_payload(value: object) -> tuple[PlanetPlacement, ...]:
    if not isinstance(value, list):
        raise TypeError("planets")
    listed: list[PlanetPlacement] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("planet")
        listed.append(
            PlanetPlacement(
                name=_text(item.get("name")),
                longitude=_float(item.get("longitude")),
                sign=_optional_text(item.get("sign")),
                element=_optional_text(item.get("element")),
                modality=_optional_text(item.get("modality")),
                ruler=_optional_text(item.get("ruler")),
                decan=_optional_int(item.get("decan")),
                decan_ruler=_optional_text(item.get("decan_ruler")),
                retrograde=_bool(item.get("retrograde")),
                exact=_bool(item.get("exact")),
            )
        )
    return tuple(listed)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("text")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("float")
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("int")
    return value


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("bool")
    return value


def _cusps(value: object) -> tuple[float, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 12:
        raise TypeError("cusps")
    return tuple(_float(item) for item in value)


def _texts(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    return _text_tuple(value)


def _text_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("texts")
    return tuple(item for item in value if isinstance(item, str))
