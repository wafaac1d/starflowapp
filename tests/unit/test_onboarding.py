from dataclasses import replace
from datetime import UTC, date, datetime, time
from uuid import UUID

import pytest
import time_machine
from pydantic import ValidationError

from starflow.bot.screens import screen_url
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import AuthFailure, FieldInvalid
from starflow.domain.onboarding import (
    next_after,
    optional_birth_time,
    parse_birth_date,
    parse_display_name,
    previous_step,
)
from starflow.domain.records import Profile
from starflow.domain.start_param import normalize_start_param
from starflow.services.profile import DraftInput, ProfileService
from starflow.services.telegram_auth import TelegramInitDataVerifier
from tests.support import make_settings
from tests.unit.test_skeleton import _init_data


def test_production_cannot_enable_dev_auth() -> None:
    with pytest.raises(ValidationError):
        make_settings(app_env="production", dev_auth_enabled=True)
    assert make_settings(app_env="local", dev_auth_enabled=True).allows_dev_auth is True
    assert make_settings(app_env="test", dev_auth_enabled=True).allows_dev_auth is False


def test_name_keeps_case_and_dates_report_the_field() -> None:
    assert parse_display_name("  Мария  ") == "Мария"
    with pytest.raises(FieldInvalid) as empty:
        parse_display_name(" ")
    assert empty.value.message_key == "errors.name_required"
    with pytest.raises(FieldInvalid) as future:
        parse_birth_date("02.01.2099", today=date(2026, 10, 21))
    assert future.value.message_key == "errors.date_future"
    with pytest.raises(FieldInvalid) as invalid:
        parse_birth_date("32.13.1990", today=date(2026, 10, 21))
    assert invalid.value.message_key == "errors.date_invalid"
    assert previous_step("date") == "name"
    assert previous_step("place") == "time"
    assert next_after("time", premium=False) == "done"
    assert next_after("time", premium=True) == "place"
    assert calendar_sign(date(1990, 1, 2)) == "козерог"


def test_start_param_keeps_case_and_drops_unsafe_values() -> None:
    assert normalize_start_param("Gift_1") == "Gift_1"
    assert normalize_start_param("gift 1") is None
    assert normalize_start_param("x" * 65) is None


def test_init_data_rejects_forgery_expiry_and_future_skew() -> None:
    token = "123456:TESTTOKEN"
    verifier = TelegramInitDataVerifier(token, max_age_sec=3600, future_skew_sec=60)
    auth_date = 1_700_000_000
    raw = _init_data(token, {"id": 7, "username": "MaKsim"}, auth_date)
    opened = datetime.fromtimestamp(auth_date + 100, tz=UTC)
    with time_machine.travel(opened, tick=False):
        assert verifier.verify(raw).username == "MaKsim"
    expired = datetime.fromtimestamp(auth_date + 4000, tz=UTC)
    with time_machine.travel(expired, tick=False), pytest.raises(AuthFailure):
        verifier.verify(raw)
    skewed = datetime.fromtimestamp(auth_date - 30, tz=UTC)
    with time_machine.travel(skewed, tick=False):
        verifier.verify(raw)
    future = datetime.fromtimestamp(auth_date - 120, tz=UTC)
    with time_machine.travel(future, tick=False), pytest.raises(AuthFailure):
        verifier.verify(raw)
    forged = raw.replace(raw[-8:], "00000000")
    with time_machine.travel(opened, tick=False), pytest.raises(AuthFailure):
        verifier.verify(forged)


def test_optional_birth_time_is_unknown_when_the_field_is_empty() -> None:
    assert optional_birth_time(None, True) == (None, True)
    assert optional_birth_time("  ", False) == (None, True)
    assert optional_birth_time("14:30", False) == (time(14, 30), False)
    with pytest.raises(FieldInvalid):
        optional_birth_time("25:00", False)


class _Profiles:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    async def ensure(self, user_id: UUID) -> Profile:
        return self.profile

    async def save_onboarding(
        self,
        user_id: UUID,
        *,
        step: str,
        display_name: str | None = None,
        birth_date: date | None = None,
        birth_time: time | None = None,
        birth_time_unknown: bool | None = None,
        timezone: str | None = None,
        clear_time: bool = False,
        clear_place: bool = False,
    ) -> Profile:
        updated = replace(self.profile, onboarding_step=step)
        if display_name is not None:
            updated = replace(updated, display_name=display_name)
        if birth_date is not None:
            updated = replace(updated, birth_date=birth_date)
        if birth_time_unknown is not None:
            updated = replace(updated, birth_time_unknown=birth_time_unknown)
        if clear_time:
            updated = replace(updated, birth_time=None)
        elif birth_time is not None:
            updated = replace(updated, birth_time=birth_time)
        if timezone is not None:
            updated = replace(updated, timezone=timezone)
        self.profile = updated
        return updated


class _Subscriptions:
    async def has_active(self, user_id: UUID, moment: datetime) -> bool:
        return False


class _Work:
    def __init__(self, profiles: _Profiles) -> None:
        self.profiles = profiles
        self.subscriptions = _Subscriptions()

    async def __aenter__(self) -> "_Work":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None


class _Zones:
    def zone(self, latitude: float, longitude: float) -> str | None:
        return None


def _draft(
    *,
    display_name: str | None = None,
    birth_date: str | None = None,
    birth_time: str | None = None,
    birth_time_unknown: bool = False,
    timezone: str | None = None,
) -> DraftInput:
    return DraftInput(
        display_name=display_name,
        birth_date=birth_date,
        birth_time=birth_time,
        birth_time_unknown=birth_time_unknown,
        timezone=timezone,
    )


async def test_blank_birth_time_finishes_registration_without_a_touch() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000041")
    profiles = _Profiles(
        Profile(
            id=user_id,
            user_id=user_id,
            display_name=None,
            birth_date=None,
            birth_time=None,
            birth_time_unknown=False,
            birth_place=None,
            latitude=None,
            longitude=None,
            timezone=None,
            onboarding_step="welcome",
        )
    )
    service = ProfileService(lambda: _Work(profiles), _Zones())
    named = await service.continue_draft(user_id, _draft(display_name="Анна"))
    assert named.onboarding_step == "date"
    assert named.display_name == "Анна"
    dated = await service.continue_draft(user_id, _draft(birth_date="12.08.1995"))
    assert dated.onboarding_step == "time"
    finished = await service.continue_draft(user_id, _draft())
    assert finished.onboarding_step == "done"
    assert finished.birth_time is None
    assert finished.birth_time_unknown is True
    assert finished.timezone == "Europe/Moscow"


def test_screen_url_keeps_the_screen_name() -> None:
    assert screen_url("https://app.example/starflow/", "paysupport") == (
        "https://app.example/starflow/paysupport"
    )
