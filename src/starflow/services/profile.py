from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import FieldInvalid, PremiumRequired
from starflow.domain.onboarding import (
    next_after,
    parse_birth_date,
    parse_birth_time,
    parse_display_name,
    parse_timezone,
    previous_step,
)
from starflow.domain.records import PlaceHit, Profile
from starflow.domain.time import now_utc
from starflow.repositories.sql import (
    GeocodeCacheRepository,
    ProfileRepository,
    SubscriptionRepository,
)


@dataclass(frozen=True)
class DraftInput:
    display_name: str | None
    birth_date: str | None
    birth_time: str | None
    birth_time_unknown: bool
    timezone: str | None


class ProfileStore(Protocol):
    profiles: ProfileRepository
    subscriptions: SubscriptionRepository
    geocodes: GeocodeCacheRepository

    async def commit(self) -> None: ...


class ProfileWork(Protocol):
    async def __aenter__(self) -> ProfileStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class TimezoneAt(Protocol):
    def zone(self, latitude: float, longitude: float) -> str | None: ...


class ProfileService:
    def __init__(
        self,
        uow_factory: Callable[[], ProfileWork],
        timezones: TimezoneAt,
        *,
        today: Callable[[], date] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._timezones = timezones
        self._today = today or _utc_today

    async def read(self, user_id: UUID) -> tuple[Profile, bool, str | None]:
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, now_utc())
            await uow.commit()
        return profile, premium, _sign(profile)

    async def continue_draft(self, user_id: UUID, incoming: DraftInput) -> Profile:
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, now_utc())
            updated = await self._advance(uow, profile, premium, incoming)
            await uow.commit()
        return updated

    async def go_back(self, user_id: UUID) -> Profile:
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            updated = await uow.profiles.save_onboarding(
                user_id, step=previous_step(profile.onboarding_step)
            )
            await uow.commit()
        return updated

    async def edit(self, user_id: UUID, incoming: DraftInput) -> Profile:
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            if profile.onboarding_step != "done":
                raise FieldInvalid("step", "errors.validation")
            updated = profile
            if incoming.display_name is not None:
                name = parse_display_name(incoming.display_name)
                updated = await uow.profiles.save_onboarding(
                    user_id, step="done", display_name=name
                )
            if incoming.birth_date is not None:
                parsed = parse_birth_date(incoming.birth_date, today=self._today())
                updated = await uow.profiles.save_onboarding(
                    user_id, step="done", birth_date=parsed
                )
            if incoming.birth_time_unknown or incoming.birth_time is not None:
                clock = parse_birth_time(incoming.birth_time, incoming.birth_time_unknown)
                updated = await uow.profiles.save_onboarding(
                    user_id,
                    step="done",
                    birth_time=clock,
                    birth_time_unknown=incoming.birth_time_unknown,
                    clear_time=incoming.birth_time_unknown,
                )
            if incoming.timezone is not None:
                zone = parse_timezone(incoming.timezone)
                updated = await uow.profiles.save_onboarding(user_id, step="done", timezone=zone)
            await uow.commit()
        return updated

    async def confirm_place(
        self,
        user_id: UUID,
        query: str,
        label: str,
        latitude: str,
        longitude: str,
    ) -> Profile:
        normalized = normalize_place_query(query)
        async with self._uow_factory() as uow:
            premium = await uow.subscriptions.has_active(user_id, now_utc())
            if not premium:
                raise PremiumRequired("place requires an active period")
            hits = await uow.geocodes.get_results(normalized)
            chosen = _matching_hit(hits, label, latitude, longitude)
            if chosen is None:
                raise FieldInvalid("birth_place", "errors.place_not_offered")
            zone = self._timezones.zone(float(chosen.latitude), float(chosen.longitude))
            if zone is None:
                raise FieldInvalid("timezone", "errors.timezone_invalid")
            parse_timezone(zone)
            await uow.profiles.ensure(user_id)
            updated = await uow.profiles.save_place(
                user_id, chosen.label, chosen.latitude, chosen.longitude, zone
            )
            await uow.commit()
        return updated

    async def _advance(
        self,
        uow: ProfileStore,
        profile: Profile,
        premium: bool,
        incoming: DraftInput,
    ) -> Profile:
        step = profile.onboarding_step
        if step == "welcome":
            return await uow.profiles.save_onboarding(profile.user_id, step="name")
        if step == "name":
            name = parse_display_name(incoming.display_name)
            return await uow.profiles.save_onboarding(
                profile.user_id, step=next_after(step, premium=premium), display_name=name
            )
        if step == "date":
            parsed = parse_birth_date(incoming.birth_date, today=self._today())
            return await uow.profiles.save_onboarding(
                profile.user_id, step=next_after(step, premium=premium), birth_date=parsed
            )
        if step == "time":
            clock = parse_birth_time(incoming.birth_time, incoming.birth_time_unknown)
            return await uow.profiles.save_onboarding(
                profile.user_id,
                step=next_after(step, premium=premium),
                birth_time=clock,
                birth_time_unknown=incoming.birth_time_unknown,
                clear_time=incoming.birth_time_unknown,
            )
        if step == "timezone":
            zone = parse_timezone(incoming.timezone)
            return await uow.profiles.save_onboarding(
                profile.user_id, step=next_after(step, premium=premium), timezone=zone
            )
        if step == "place":
            raise FieldInvalid("birth_place", "errors.place_required")
        return profile


def _sign(profile: Profile) -> str | None:
    if profile.onboarding_step != "done" or profile.birth_date is None:
        return None
    return calendar_sign(profile.birth_date)


def _utc_today() -> date:
    return now_utc().date()


def normalize_place_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def _matching_hit(
    hits: list[PlaceHit] | None,
    label: str,
    latitude: str,
    longitude: str,
) -> PlaceHit | None:
    if hits is None:
        return None
    for hit in hits:
        if hit.label == label and str(hit.latitude) == latitude and str(hit.longitude) == longitude:
            return hit
    return None
