import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest
import time_machine
from pydantic import ValidationError

from starflow.astro.ecliptic import sign_for_longitude
from starflow.bootstrap import build_container
from starflow.bot.session import InactiveTelegramSession
from starflow.domain.errors import AuthFailure
from starflow.domain.profile import ensure_birth_time
from starflow.domain.time import local_date
from starflow.i18n.guard import assert_authored, redact
from starflow.services.telegram_auth import (
    TelegramInitDataVerifier,
    read_signed_payload,
    sign_payload,
)
from tests.support import make_settings

ROOT = Path(__file__).resolve().parents[2]


def test_worker_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(web_concurrency=2)


def test_polling_is_the_default_and_webhook_needs_a_secret() -> None:
    polling = make_settings()
    assert polling.bot_mode == "polling"
    assert polling.webhook_path == ""
    with pytest.raises(ValidationError):
        make_settings(webhook_url="https://example.com/telegram/webhook", webhook_secret="")
    webhook = make_settings(
        webhook_url="https://example.com/telegram/webhook",
        webhook_secret="s" * 16,
        app_env="production",
    )
    assert webhook.bot_mode == "webhook"
    assert webhook.webhook_path == "/telegram/webhook"


def test_subscription_price_comes_from_the_environment() -> None:
    priced = make_settings(premium_price_stars=1)
    assert priced.runtime_plans().premium.price_stars == 1
    with pytest.raises(ValidationError):
        make_settings(premium_price_stars=0)
    with pytest.raises(ValidationError):
        make_settings(premium_price_stars=10001)


def test_example_env_names_the_verified_models() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DEEPSEEK_MODEL_FAST=deepseek-flash\n" in text
    assert "DEEPSEEK_MODEL_PRO=deepseek-v4-pro\n" in text
    assert "DEEPSEEK_BASE_URL=https://api.deepseek.com\n" in text
    names = [
        line.split("=", 1)[0]
        for line in text.splitlines()
        if line and not line.startswith("#") and "=" in line
    ]
    assert names
    assert all(not name.startswith("VITE_") for name in names)


def test_entrypoint_and_compose_keep_one_worker_and_two_services() -> None:
    entry = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "--workers 1" in entry
    assert "alembic upgrade head" in entry
    assert 'WEB_CONCURRENCY:-1}" != "1"' in entry
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:16" in compose
    assert "pg_isready" in compose
    assert "service_healthy" in compose
    assert compose.count("image:") + compose.count("build:") == 2


def test_sign_longitude_wraps_the_ecliptic() -> None:
    assert sign_for_longitude(0) == "овен"
    assert sign_for_longitude(30) == "телец"
    assert sign_for_longitude(359.9) == "рыбы"
    assert sign_for_longitude(-1) == "рыбы"


def test_unknown_birth_time_rejects_a_clock_time() -> None:
    from datetime import time

    from starflow.domain.errors import BirthTimeInvalid

    ensure_birth_time(None, True)
    with pytest.raises(BirthTimeInvalid):
        ensure_birth_time(time(1, 2), True)


def test_local_date_uses_the_profile_zone() -> None:
    with time_machine.travel(datetime(2026, 10, 21, 22, 30, tzinfo=UTC), tick=False):
        from starflow.domain.time import now_utc

        assert local_date(now_utc(), "Europe/Moscow") == datetime(2026, 10, 22, tzinfo=UTC).date()


def test_authored_text_and_redaction() -> None:
    assert_authored("строчный текст")
    with pytest.raises(ValueError):
        assert_authored("Заглавная")
    cleaned = redact(
        {"bot_token": "secret", "nested": {"birth_date": "2000-01-01"}, "ok": "Bearer abc"}
    )
    assert cleaned == {
        "bot_token": "[redacted]",
        "nested": {"birth_date": "[redacted]"},
        "ok": "Bearer [redacted]",
    }


def test_init_data_signature_and_username_case() -> None:
    token = "123456:TESTTOKEN"
    verifier = TelegramInitDataVerifier(token, max_age_sec=3600)
    raw = _init_data(token, {"id": 7, "username": "MaKsim"}, 1_700_000_000)
    with time_machine.travel(datetime.fromtimestamp(1_700_000_100, tz=UTC), tick=False):
        identity = verifier.verify(raw)
    assert identity.telegram_id == 7
    assert identity.username == "MaKsim"
    with pytest.raises(AuthFailure):
        verifier.verify(raw + "broken")


def test_payload_signature_roundtrip() -> None:
    secret = "p" * 32
    signed = sign_payload("order-1", secret)
    assert read_signed_payload(signed, secret) == "order-1"
    with pytest.raises(AuthFailure):
        read_signed_payload(signed + "x", secret)


def test_frontend_sources_do_not_receive_secrets() -> None:
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "VITE_" not in text
        assert "BOT_TOKEN" not in text
        assert "DEEPSEEK_API_KEY" not in text
        assert "initDataUnsafe" not in text


@pytest.mark.asyncio
async def test_lifecycle_closes_the_single_bot_and_scheduler() -> None:
    container = build_container(make_settings(bot_retry_sec=30))
    await container.startup()
    try:
        await asyncio.sleep(0.05)
        assert container.bot_runtime is not None
        assert container.scheduler_runtime is not None
    finally:
        await container.shutdown()
    session = container.bot.session
    assert isinstance(session, InactiveTelegramSession)
    assert session.closed is True


def test_resource_files_are_lowercase() -> None:
    for path in (ROOT / "resources").rglob("*"):
        if path.suffix not in {".yaml", ".txt"}:
            continue
        assert_authored(path.read_text(encoding="utf-8"))


def _init_data(
    token: str,
    user: dict[str, object],
    auth_date: int,
    extra: dict[str, str] | None = None,
) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps(user, separators=(",", ":")),
    }
    if extra is not None:
        values.update(extra)
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": digest})
