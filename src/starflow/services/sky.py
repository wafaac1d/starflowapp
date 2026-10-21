"""Общее небо даты. Считается один раз на полдень UTC и переиспользуется."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Protocol

from starflow.astro.swiss import BodyPosition, SwissEphemeris
from starflow.domain.astrology import facts_for_longitude, phase_name
from starflow.domain.errors import Conflict
from starflow.domain.time import now_utc
from starflow.repositories.sql import DailySkyRepository


class SkyStore(Protocol):
    daily_sky: DailySkyRepository

    async def commit(self) -> None: ...


class SkyWork(Protocol):
    async def __aenter__(self) -> SkyStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class SkyService:
    def __init__(self, uow_factory: Callable[[], SkyWork], ephemeris: SwissEphemeris) -> None:
        self._uow_factory = uow_factory
        self._ephemeris = ephemeris

    async def for_date(self, day: date) -> dict[str, object]:
        async with self._uow_factory() as uow:
            stored = await uow.daily_sky.get(day)
            if stored is not None:
                return stored
        payload = _payload(self._ephemeris, day)
        try:
            async with self._uow_factory() as uow:
                stored = await uow.daily_sky.get(day)
                if stored is not None:
                    return stored
                await uow.daily_sky.put(day, payload, now_utc())
                await uow.commit()
        except Conflict:
            async with self._uow_factory() as uow:
                stored = await uow.daily_sky.get(day)
            if stored is None:
                raise
            return stored
        return payload


def _payload(ephemeris: SwissEphemeris, day: date) -> dict[str, object]:
    moment = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    bodies: tuple[BodyPosition, ...] = ephemeris.positions(moment)
    by_name = {body.name: body for body in bodies}
    sun = by_name["солнце"]
    moon = by_name["луна"]
    listed: list[dict[str, object]] = []
    for body in bodies:
        facts = facts_for_longitude(body.longitude)
        listed.append(
            {
                "name": body.name,
                "longitude": body.longitude,
                "sign": facts.sign,
                "retrograde": body.retrograde,
            }
        )
    return {
        "sun_sign": facts_for_longitude(sun.longitude).sign,
        "moon_sign": facts_for_longitude(moon.longitude).sign,
        "phase_name": phase_name(sun.longitude, moon.longitude),
        "bodies": listed,
    }
