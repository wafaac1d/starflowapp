"""Apply migrations to an empty PostgreSQL and exercise the repositories."""

import os
import subprocess
import sys
import time as unix_clock
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from starflow.api.app import build_fastapi
from starflow.bootstrap import build_container
from starflow.config import Settings
from starflow.db.engine import create_session_factory
from starflow.db.tables import Base, UserRow
from starflow.domain.errors import Conflict, QuotaExceeded
from starflow.domain.records import ProfileDraft
from starflow.repositories.uow import SqlUnitOfWork
from tests.support import make_settings
from tests.unit.test_skeleton import _init_data

ROOT = Path(__file__).resolve().parents[2]


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    raise RuntimeError(f"unsupported database url {url}")


def _alembic(url: str, *args: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "BOT_TOKEN": "123456:TESTTOKEN",
            "ADMIN_IDS": "1",
            "DATABASE_URL": url,
            "DEEPSEEK_API_KEY": "test-deepseek-key",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_MODEL_FAST": "deepseek-flash",
            "DEEPSEEK_MODEL_PRO": "deepseek-v4-pro",
            "PREMIUM_PRICE_STARS": "250",
            "PAYMENT_HMAC_SECRET": "p" * 32,
            "AUTH_SESSION_SECRET": "a" * 32,
            "APP_ENV": "test",
            "SINGLETON_LOCK": "false",
            "WEBHOOK_URL": "",
            "WEBHOOK_SECRET": "",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)


@pytest.fixture(scope="module")
def database_url() -> str:
    with PostgresContainer("postgres:16") as postgres:
        url = _asyncpg_url(postgres.get_connection_url())
        _alembic(url, "upgrade", "head")
        yield url


def test_migrations_roundtrip_from_empty(database_url: str) -> None:
    _alembic(database_url, "downgrade", "base")
    _alembic(database_url, "upgrade", "head")
    _alembic(database_url, "upgrade", "head")


@pytest.mark.asyncio
async def test_repositories_constraints_and_billing_survival(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    assert set(Base.metadata.tables) <= names
    assert "flow_states" not in names

    factory = create_session_factory(engine)
    moment = datetime(2026, 10, 21, 12, tzinfo=UTC)
    async with SqlUnitOfWork(factory) as uow:
        user = await uow.users.upsert_telegram(42, "MaKsim", "ru")
        again = await uow.users.upsert_telegram(42, "MaKsim", "ru")
        assert again.id == user.id
        assert again.username == "MaKsim"
        profile = await uow.profiles.upsert(
            user.id,
            ProfileDraft(
                display_name="Мария",
                birth_date=date(1990, 1, 2),
                birth_time=None,
                birth_time_unknown=True,
                birth_place=None,
                latitude=None,
                longitude=None,
                timezone="Europe/Moscow",
            ),
        )
        assert profile.birth_time is None
        related = await uow.related_profiles.add(
            user.id,
            ProfileDraft(
                display_name="друг",
                birth_date=date(1991, 2, 3),
                birth_time=time(8, 30),
                birth_time_unknown=False,
                birth_place="казань",
                latitude=Decimal("55.788700"),
                longitude=Decimal("49.122100"),
                timezone="Europe/Moscow",
            ),
        )
        subscription = await uow.subscriptions.add(
            user.id, "premium", "active", moment, moment, "payment"
        )
        await uow.subscription_events.add(subscription, user.id, "opened", {"source": "payment"})
        order = await uow.orders.add(user.id, "premium", 250, "XTR", "paid", "payload-1")
        charge = await uow.charges.add(
            order.id,
            user.id,
            "charge-1",
            250,
            "XTR",
            moment,
            moment,
            moment,
            {"currency": "XTR"},
        )
        counter = await uow.usage.open_counter(user.id, "assistant", moment, moment, 1)
        await uow.usage.increment(counter.id)
        history = await uow.forecast_history.add(
            user.id, "day", date(2026, 10, 21), {"tone": "calm"}
        )
        await uow.forecast_cache.put("day:1", user.id, "day", {"tone": "calm"}, moment)
        await uow.favorites.add(user.id, "forecast", history)
        await uow.notification_settings.upsert(user.id, True, time(9, 0), "Europe/Moscow")
        await uow.assistant_messages.add(user.id, "user", "вопрос", moment)
        await uow.feedback.add(user.id, history, 5, None)
        await uow.ai_requests.add(user.id, "deepseek-flash", "assistant", "recorded")
        await uow.geocodes.put("казань", Decimal("55.788700"), Decimal("49.122100"), "казань", {})
        await uow.daily_sky.put(date(2026, 10, 21), {"moon": "growing"}, moment)
        await uow.gifts.add("GIFT1", user.id, "premium", "pending", charge.id)
        await uow.outbox.enqueue(user.id, "digest", "bot.digest", date(2026, 10, 21), moment)
        await uow.commit()
        user_id = user.id
        charge_id = charge.id
        order_id = order.id
        related_id = related

    async with SqlUnitOfWork(factory) as uow:
        with pytest.raises(Conflict):
            await uow.charges.add(
                order_id,
                user_id,
                "charge-1",
                250,
                "XTR",
                moment,
                moment,
                moment,
                {},
            )
        with pytest.raises(QuotaExceeded):
            stored = await uow.usage.open_counter(user_id, "assistant-2", moment, moment, 1)
            await uow.usage.increment(stored.id)
            await uow.usage.increment(stored.id)
        await uow.users.delete(user_id)
        await uow.commit()

    async with SqlUnitOfWork(factory) as uow:
        assert await uow.users.get_by_telegram_id(42) is None
        assert await uow.profiles.get_by_user_id(user_id) is None
        surviving = await uow.charges.get(charge_id)
        assert surviving is not None
        assert surviving.user_id is None
        assert surviving.telegram_payment_charge_id == "charge-1"
        kept_order = await uow.orders.get(order_id)
        assert kept_order is not None
        assert kept_order.user_id is None
    assert related_id is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_http_smoke_does_not_turn_missing_routes_into_html(
    database_url: str, tmp_path: Path
) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>starflow</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    settings = make_settings(
        database_url=database_url,
        singleton_lock=True,
        frontend_dist=dist,
        logo_path=ROOT / "static" / "logo.png",
        bot_retry_sec=30,
    )
    app = build_fastapi(build_container(settings))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        live = await client.get("/liveness")
        ready = await client.get("/readiness")
        health = await client.get("/health")
        meta = await client.get("/api/v1/meta")
        missing_api = await client.get("/api/v1/missing")
        missing_asset = await client.get("/assets/missing.js")
        asset = await client.get("/assets/app.js")
        client_route = await client.get("/reading")
        logo = await client.get("/logo.png")
        webhook = await client.post("/telegram/webhook", json={"update_id": 1})
        raw = _init_data(
            settings.bot_token,
            {"id": 99, "username": "Ada"},
            int(unix_clock.time()),
        )
        session = await client.post(
            "/api/v1/session",
            headers={"Authorization": f"TMA {raw}", "X-Starflow-Request": "1"},
        )
        again = await client.post(
            "/api/v1/session",
            headers={"Authorization": f"TMA {raw}", "X-Starflow-Request": "1"},
        )
        current = await client.get("/api/v1/session")
        missing_intent = await client.post(
            "/api/v1/session",
            headers={"Authorization": f"TMA {raw}"},
        )
    assert live.status_code == 200
    assert ready.status_code == 200
    assert health.status_code == 200
    assert health.json()["status"] == "ready"
    assert meta.json()["premium_price_stars"] == 250
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert not missing_api.content.lstrip().startswith(b"<")
    assert missing_asset.status_code == 404
    assert not missing_asset.content.lstrip().startswith(b"<")
    assert asset.status_code == 200
    assert client_route.status_code == 200
    assert client_route.content.lstrip().startswith(b"<!doctype html>")
    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/png")
    assert webhook.status_code == 404
    assert session.status_code == 200
    assert again.status_code == 200
    assert session.json()["step"] == "welcome"
    assert session.json()["is_admin"] is False
    assert "token" not in session.json()
    assert "httponly" in session.headers["set-cookie"].lower()
    assert current.status_code == 200
    assert missing_intent.status_code == 403


@pytest.mark.asyncio
async def test_onboarding_resumes_and_rows_stay_with_their_owner(
    database_url: str,
) -> None:
    settings = make_settings(
        database_url=database_url,
        singleton_lock=False,
        dev_auth_enabled=True,
        bot_retry_sec=30,
    )
    app = build_fastapi(build_container(settings))
    transport = ASGITransport(app=app)
    intent = {"X-Starflow-Request": "1"}
    async with AsyncClient(transport=transport, base_url="http://test") as owner:
        opened = await _exchange(owner, settings, 41, "Gift_1")
        assert opened.status_code == 200
        assert opened.json()["is_premium"] is False
        named = await owner.post("/api/v1/profile/draft", headers=intent, json={})
        assert named.status_code == 200
        assert named.json()["step"] == "name"
        saved = await owner.post(
            "/api/v1/profile/draft",
            headers=intent,
            json={"display_name": "Мария"},
        )
        assert saved.json()["display_name"] == "Мария"
        bad = await owner.post(
            "/api/v1/profile/draft",
            headers=intent,
            json={"birth_date": "32.13.1990"},
        )
        assert bad.status_code == 422
        assert "birth_date" in bad.json()["fields"]
        backed = await owner.post("/api/v1/profile/back", headers=intent)
        assert backed.json()["step"] == "name"
        assert backed.json()["display_name"] == "Мария"
        async with AsyncClient(transport=transport, base_url="http://test") as resumed:
            again = await _exchange(resumed, settings, 41, None)
        assert again.json()["step"] == "name"
        assert again.json()["display_name"] == "Мария"
        await owner.post("/api/v1/profile/draft", headers=intent, json={"display_name": "Мария"})
        await owner.post("/api/v1/profile/draft", headers=intent, json={"birth_date": "02.01.1990"})
        await owner.post("/api/v1/profile/draft", headers=intent, json={"birth_time_unknown": True})
        done = await owner.post(
            "/api/v1/profile/draft",
            headers=intent,
            json={"timezone": "Europe/Moscow"},
        )
        assert done.status_code == 200
        assert done.json()["step"] == "done"
        assert done.json()["calendar_sign"] == "козерог"
        owner_id = UUID(opened.json()["user_id"])
        engine = create_async_engine(database_url)
        factory = create_session_factory(engine)
        async with factory() as session:
            row = (
                await session.execute(select(UserRow).where(UserRow.telegram_id == 41))
            ).scalar_one()
            assert row.pending_start_param == "Gift_1"
        moment = datetime(2026, 10, 21, tzinfo=UTC)
        async with SqlUnitOfWork(factory) as uow:
            history_id = await uow.forecast_history.add(owner_id, "day", date(2026, 10, 21), {})
            message_id = await uow.assistant_messages.add(owner_id, "user", "заметка", moment)
            order = await uow.orders.add(
                owner_id, "premium", 250, "XTR", "pending", "payload-owner-41"
            )
            await uow.commit()
        async with AsyncClient(transport=transport, base_url="http://test") as stranger:
            foreign = await _exchange(stranger, settings, 42, None)
            assert foreign.json()["is_admin"] is False
            assert (await stranger.get(f"/api/v1/history/{history_id}")).status_code == 404
            assert (
                await stranger.get(f"/api/v1/assistant/messages/{message_id}")
            ).status_code == 404
            assert (await stranger.get(f"/api/v1/orders/{order.id}")).status_code == 404
            assert (await stranger.get("/api/v1/admin/status")).status_code == 404
        seen = await owner.get(f"/api/v1/history/{history_id}?user_id={foreign.json()['user_id']}")
        assert seen.status_code == 200
        assert (await owner.get(f"/api/v1/assistant/messages/{message_id}")).status_code == 200
        assert (await owner.get(f"/api/v1/orders/{order.id}")).status_code == 200
        blocked = await owner.post(
            "/api/v1/session/dev",
            headers={**intent, "X-Starflow-Dev-User": "5"},
        )
        assert blocked.status_code == 404
        logged_out = await owner.post("/api/v1/session/logout", headers=intent)
        assert logged_out.status_code == 200
        assert (await owner.get("/api/v1/session")).status_code == 401
        await engine.dispose()
    local_settings = make_settings(
        database_url=database_url,
        app_env="local",
        dev_auth_enabled=True,
        singleton_lock=False,
        bot_retry_sec=30,
    )
    local_app = build_fastapi(build_container(local_settings))
    async with AsyncClient(
        transport=ASGITransport(app=local_app),
        base_url="http://test",
    ) as local:
        dev = await local.post(
            "/api/v1/session/dev",
            headers={**intent, "X-Starflow-Dev-User": "8"},
        )
        assert dev.status_code == 200
        assert dev.json()["step"] == "welcome"
        admin = await local.post(
            "/api/v1/session/dev",
            headers={**intent, "X-Starflow-Dev-User": "1"},
        )
        assert (await local.get("/api/v1/admin/status")).status_code == 200
        assert admin.json()["is_admin"] is True


async def _exchange(
    client: AsyncClient, settings: Settings, telegram_id: int, start: str | None
) -> Response:
    extra = None if start is None else {"start_param": start}
    raw = _init_data(
        settings.bot_token,
        {"id": telegram_id, "username": "Ada"},
        int(unix_clock.time()),
        extra,
    )
    return await client.post(
        "/api/v1/session",
        headers={"Authorization": f"TMA {raw}", "X-Starflow-Request": "1"},
    )
