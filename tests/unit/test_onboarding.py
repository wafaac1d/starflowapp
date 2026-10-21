from datetime import UTC, date, datetime

import pytest
import time_machine
from pydantic import ValidationError

from starflow.bot.screens import screen_url
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import AuthFailure, FieldInvalid
from starflow.domain.onboarding import parse_birth_date, parse_display_name, previous_step
from starflow.domain.start_param import normalize_start_param
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


def test_screen_url_keeps_the_screen_name() -> None:
    assert screen_url("https://app.example/starflow/", "paysupport") == (
        "https://app.example/starflow/paysupport"
    )
