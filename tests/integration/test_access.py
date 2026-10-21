"""Квоты, источники premium и идемпотентность HTTP на пустой PostgreSQL."""

import asyncio
import os
import subprocess
import sys
import time as unix_clock
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from starflow.api.app import build_fastapi
from starflow.bootstrap import build_container
from starflow.db.engine import create_db_engine, create_session_factory
from starflow.db.tables import (
    DailySkyRow,
    FavoriteRow,
    ForecastCacheRow,
    ForecastHistoryRow,
    IdempotencyKeyRow,
    UsageCounterRow,
)
from starflow.domain.plans import Plans, load_plans
from starflow.domain.quota import Allowed, LimitReached
from starflow.domain.records import ProfileDraft
from starflow.repositories.uow import SqlUnitOfWork
from starflow.services.quota import QuotaService, StoredResult
from tests.support import make_settings
from tests.unit.test_skeleton import _init_data

ROOT = Path(__file__).resolve().parents[2]


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _alembic(url: str) -> None:
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
        [sys.executable, "-m", "alembic", "upgrade", "head"],
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
        _alembic(url)
        yield url


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_db_engine(url)
    return engine, create_session_factory(engine)


def _draft(moment: date = date(1990, 1, 2)) -> ProfileDraft:
    return ProfileDraft(
        display_name="мария",
        birth_date=moment,
        birth_time=None,
        birth_time_unknown=True,
        birth_place=None,
        latitude=None,
        longitude=None,
        timezone="Europe/Moscow",
    )


async def _user(factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with SqlUnitOfWork(factory) as uow:
        user = await uow.users.upsert_telegram(unix_clock.time_ns() % 1_000_000_000, None, "ru")
        await uow.profiles.upsert(user.id, _draft())
        await uow.commit()
        return user.id


def _plans() -> Plans:
    return load_plans(ROOT / "resources" / "plans.yaml")


@pytest.mark.asyncio
async def test_premium_sources_stay_independent(database_url: str) -> None:
    engine, factory = _factory(database_url)
    now = datetime(2026, 6, 15, tzinfo=UTC)
    service = QuotaService(lambda: SqlUnitOfWork(factory), _plans(), clock=lambda: now)
    user_id = await _user(factory)
    async with SqlUnitOfWork(factory) as uow:
        await uow.subscriptions.add(
            user_id,
            "premium",
            "active",
            now - timedelta(days=1),
            now + timedelta(days=10),
            "payment",
        )
        await uow.commit()
        assert await uow.subscriptions.has_active(user_id, now) is False
    async with SqlUnitOfWork(factory) as uow:
        gift = await uow.subscriptions.add(
            user_id,
            "premium",
            "active",
            now - timedelta(days=1),
            now + timedelta(days=5),
            "gift",
        )
        subscription = await uow.subscriptions.add(
            user_id,
            "premium",
            "active",
            now - timedelta(days=40),
            now - timedelta(days=1),
            "subscription",
            grace_until=now + timedelta(days=3),
        )
        await uow.commit()
    async with SqlUnitOfWork(factory) as uow:
        await uow.subscriptions.revoke(subscription, now)
        await uow.commit()
        assert await uow.subscriptions.has_active(user_id, now) is True
        await uow.subscriptions.revoke(gift, now)
        await uow.commit()
        assert await uow.subscriptions.has_active(user_id, now) is False
        await uow.subscriptions.add(
            user_id,
            "premium",
            "active",
            now - timedelta(days=10),
            now - timedelta(days=1),
            "trial",
            grace_until=now + timedelta(days=4),
        )
        await uow.commit()
        assert await uow.subscriptions.has_active(user_id, now) is False
        await uow.subscriptions.add(
            user_id,
            "premium",
            "active",
            now - timedelta(days=40),
            now - timedelta(days=1),
            "subscription",
            grace_until=now + timedelta(days=2),
        )
        await uow.commit()
    natal = await service.preview(user_id, "natal")
    assert isinstance(natal, Allowed)
    assistant = await service.preview(user_id, "assistant")
    assert isinstance(assistant, LimitReached)
    assert assistant.reset_at == now - timedelta(days=1)
    await engine.dispose()


@pytest.mark.asyncio
async def test_paid_period_questions_do_not_roll_into_grace_or_the_next_grant(
    database_url: str,
) -> None:
    engine, factory = _factory(database_url)
    now = datetime(2026, 6, 15, tzinfo=UTC)
    service = QuotaService(lambda: SqlUnitOfWork(factory), _plans(), clock=lambda: now)
    user_id = await _user(factory)
    async with SqlUnitOfWork(factory) as uow:
        first = await uow.subscriptions.add(
            user_id, "premium", "active", now - timedelta(days=5), now + timedelta(days=10), "gift"
        )
        await uow.commit()

    async def producer(_store: object) -> dict[str, object]:
        return {"answer": "ok"}

    opened = await service.execute(user_id, "assistant", "question-1", producer)
    assert isinstance(opened, StoredResult)
    async with factory() as session:
        row = (
            await session.execute(select(UsageCounterRow).where(UsageCounterRow.user_id == user_id))
        ).scalar_one()
        row.used = 20
        row.reserved = 0
        await session.commit()
    blocked = await service.preview(user_id, "assistant")
    assert isinstance(blocked, LimitReached)
    async with SqlUnitOfWork(factory) as uow:
        await uow.subscriptions.add(
            user_id,
            "premium",
            "active",
            now - timedelta(days=1),
            now + timedelta(days=30),
            "admin",
        )
        await uow.commit()
    renewed = await service.execute(user_id, "assistant", "question-2", producer)
    assert isinstance(renewed, StoredResult)
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(UsageCounterRow).where(UsageCounterRow.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 2
    assert {row.used for row in rows} == {20, 1}
    assert first is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_week_resets_on_monday_and_a_failure_releases_the_hold(
    database_url: str,
) -> None:
    engine, factory = _factory(database_url)
    moment = datetime(2026, 10, 19, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    clock = {"now": moment}
    service = QuotaService(
        lambda: SqlUnitOfWork(factory),
        _plans(),
        clock=lambda: clock["now"],
    )
    user_id = await _user(factory)

    async def ok(_store: object) -> dict[str, object]:
        return {"ok": True}

    async def fail(_store: object) -> dict[str, object]:
        raise RuntimeError("delivery failed")

    with pytest.raises(RuntimeError):
        await service.execute(user_id, "compatibility", "compat-fail", fail)
    first = await service.execute(user_id, "compatibility", "compat-one1", ok)
    second = await service.execute(user_id, "compatibility", "compat-two2", ok)
    assert isinstance(first, StoredResult)
    assert isinstance(second, LimitReached)
    clock["now"] = moment + timedelta(days=7)
    third = await service.execute(user_id, "compatibility", "compat-three", ok)
    assert isinstance(third, StoredResult)
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(UsageCounterRow).where(UsageCounterRow.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 2
    assert all(row.used == 1 and row.reserved == 0 for row in rows)
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_reserve_keeps_a_single_charge(database_url: str) -> None:
    engine, factory = _factory(database_url)
    service = QuotaService(
        lambda: SqlUnitOfWork(factory),
        _plans(),
        clock=lambda: datetime(2026, 10, 21, 12, tzinfo=UTC),
    )
    user_id = await _user(factory)

    async def producer(_store: object) -> dict[str, object]:
        await asyncio.sleep(0.05)
        return {"ok": True}

    left, right = await asyncio.gather(
        service.execute(user_id, "compatibility", "race-left1", producer),
        service.execute(user_id, "compatibility", "race-right2", producer),
    )
    outcomes = (left, right)
    assert sum(isinstance(item, StoredResult) for item in outcomes) == 1
    assert sum(isinstance(item, LimitReached) for item in outcomes) == 1
    async with factory() as session:
        row = (
            await session.execute(select(UsageCounterRow).where(UsageCounterRow.user_id == user_id))
        ).scalar_one()
    assert row.used == 1
    assert row.reserved == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_http_idempotency_favorites_and_chart_paywall(database_url: str) -> None:
    engine, factory = _factory(database_url)
    settings = make_settings(database_url=database_url, singleton_lock=False)
    container = build_container(settings)
    app = build_fastapi(container)
    raw = _init_data(settings.bot_token, {"id": 501, "username": "quota"}, int(unix_clock.time()))
    intent = {"X-Starflow-Request": "1"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        opened = await client.post(
            "/api/v1/session",
            headers={"Authorization": f"TMA {raw}", **intent},
        )
        assert opened.status_code == 200
        user_id = UUID(opened.json()["user_id"])
        async with SqlUnitOfWork(factory) as uow:
            await uow.profiles.upsert(user_id, _draft())
            histories = []
            for day in range(1, 5):
                histories.append(
                    await uow.forecast_history.add(
                        user_id,
                        "day",
                        date(2026, 10, day),
                        {"tone": "calm"},
                    )
                )
            await uow.commit()
        access = await client.get("/api/v1/access/natal")
        chart = await client.get("/api/v1/chart")
        async with factory() as session:
            usage_before = await session.scalar(
                select(func.count())
                .select_from(UsageCounterRow)
                .where(UsageCounterRow.user_id == user_id)
            )
            holds_before = await session.scalar(
                select(func.count())
                .select_from(IdempotencyKeyRow)
                .where(IdempotencyKeyRow.user_id == user_id)
            )
        missing_key = await client.post(
            "/api/v1/favorites",
            headers=intent,
            json={"target_id": str(histories[0])},
        )
        short_key = await client.post(
            "/api/v1/favorites",
            headers={**intent, "Idempotency-Key": "short"},
            json={"target_id": str(histories[0])},
        )
        saved = await client.post(
            "/api/v1/favorites",
            headers={**intent, "Idempotency-Key": "favorite-1"},
            json={"target_id": str(histories[0])},
        )
        replay = await client.post(
            "/api/v1/favorites",
            headers={**intent, "Idempotency-Key": "favorite-1"},
            json={"target_id": str(histories[0])},
        )
        conflict = await client.post(
            "/api/v1/favorites",
            headers={**intent, "Idempotency-Key": "favorite-1b"},
            json={"target_id": str(histories[0])},
        )
        for index, history in enumerate(histories[1:3], start=2):
            added = await client.post(
                "/api/v1/favorites",
                headers={**intent, "Idempotency-Key": f"favorite-{index}"},
                json={"target_id": str(history)},
            )
            assert added.status_code == 200
        limited = await client.post(
            "/api/v1/favorites",
            headers={**intent, "Idempotency-Key": "favorite-4"},
            json={"target_id": str(histories[3])},
        )
        refused = await client.post(
            "/api/v1/compatibility",
            headers={**intent, "Idempotency-Key": "compat-none"},
        )
        async with SqlUnitOfWork(factory) as uow:
            await uow.related_profiles.add(
                user_id,
                ProfileDraft(
                    display_name="друг",
                    birth_date=date(1991, 2, 3),
                    birth_time=time(8, 30),
                    birth_time_unknown=False,
                    birth_place=None,
                    latitude=None,
                    longitude=None,
                    timezone="Europe/Moscow",
                ),
            )
            await uow.commit()
        matched = await client.post(
            "/api/v1/compatibility",
            headers={**intent, "Idempotency-Key": "compat-yes1"},
        )
        matched_again = await client.post(
            "/api/v1/compatibility",
            headers={**intent, "Idempotency-Key": "compat-yes1"},
        )
        matched_other = await client.post(
            "/api/v1/compatibility",
            headers={**intent, "Idempotency-Key": "compat-yes2"},
        )
    assert access.status_code == 200
    assert access.json()["decision"] == "premium_required"
    assert usage_before == 0
    assert holds_before == 0
    assert chart.status_code == 200
    body = chart.json()
    assert body["sun_sign"] == "козерог"
    assert body["sun_sign_source"] == "calendar"
    assert body["moon_sign"] is None
    assert body["houses"] is None
    assert "time_unknown" in body["limitations"]
    assert body["natal_access"] == "premium_required"
    assert missing_key.status_code == 422
    assert short_key.status_code == 422
    assert saved.status_code == 200
    assert saved.json()["replayed"] is False
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["favorite_id"] == saved.json()["favorite_id"]
    assert conflict.status_code == 409
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "limit_reached"
    assert "reset_at" not in limited.json()
    assert refused.status_code == 422
    assert matched.status_code == 200
    assert matched.json()["replayed"] is False
    assert matched_again.json()["replayed"] is True
    assert matched_again.json()["history_id"] == matched.json()["history_id"]
    assert matched_other.status_code == 429
    assert "reset_at" in matched_other.json()
    async with factory() as session:
        favorites = await session.scalar(
            select(func.count()).select_from(FavoriteRow).where(FavoriteRow.user_id == user_id)
        )
        histories = await session.scalar(
            select(func.count())
            .select_from(ForecastHistoryRow)
            .where(
                ForecastHistoryRow.user_id == user_id,
                ForecastHistoryRow.kind == "compatibility",
            )
        )
        counter = (
            await session.execute(
                select(UsageCounterRow).where(
                    UsageCounterRow.user_id == user_id,
                    UsageCounterRow.counter_key == "compatibility",
                )
            )
        ).scalar_one()
        keys = (
            (
                await session.execute(
                    select(IdempotencyKeyRow).where(IdempotencyKeyRow.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
    assert favorites == 3
    assert histories == 1
    assert counter.used == 1
    assert counter.reserved == 0
    assert all(row.status != "reserved" for row in keys)
    await container.engine.dispose()
    await engine.dispose()


@pytest.mark.asyncio
async def test_daily_sky_is_computed_once_and_birth_edits_drop_the_chart(
    database_url: str,
) -> None:
    engine, factory = _factory(database_url)
    settings = make_settings(database_url=database_url, singleton_lock=False)
    container = build_container(settings)
    day = date(2026, 5, 1)
    first, second = await asyncio.gather(
        container.sky_service.for_date(day),
        container.sky_service.for_date(day),
    )
    assert first["sun_sign"] == second["sun_sign"]
    user_id = await _user(factory)
    async with SqlUnitOfWork(factory) as uow:
        await uow.forecast_cache.put(
            "natal:stale",
            user_id,
            "natal",
            {"sun_sign": "овен"},
            datetime(2027, 1, 1, tzinfo=UTC),
        )
        await uow.profiles.save_onboarding(user_id, step="done", birth_date=date(1992, 8, 1))
        await uow.commit()
    async with factory() as session:
        skies = await session.scalar(
            select(func.count()).select_from(DailySkyRow).where(DailySkyRow.sky_date == day)
        )
        cached = await session.scalar(
            select(func.count())
            .select_from(ForecastCacheRow)
            .where(ForecastCacheRow.user_id == user_id, ForecastCacheRow.kind == "natal")
        )
    assert skies == 1
    assert cached == 0
    await container.engine.dispose()
    await engine.dispose()
