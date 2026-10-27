"""Аренда outbox, рассылка только из кэша, админ и удаление."""

import os
import subprocess
import sys
import time as unix_clock
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from starflow.ai.catalog import load_prompts
from starflow.api.app import build_fastapi
from starflow.bootstrap import build_container
from starflow.cache.memory import MemoryCache
from starflow.db.engine import create_db_engine, create_session_factory
from starflow.db.tables import NotificationOutboxRow, OrderRow, PaymentChargeRow, UserRow
from starflow.domain.errors import DeliveryBlocked, DeliveryRetry
from starflow.domain.records import ProfileDraft
from starflow.domain.segments import forecast_cache_key, moon_segment, period_key
from starflow.domain.time import local_date
from starflow.i18n.catalog import load_catalog
from starflow.repositories.uow import SqlUnitOfWork
from starflow.services.ops import OpsService
from starflow.services.outbox import OutboxService
from starflow.services.pace import SendPace
from tests.support import make_settings
from tests.unit.test_skeleton import _init_data

ROOT = Path(__file__).resolve().parents[2]
MOMENT = datetime(2026, 6, 15, 6, 10, tzinfo=UTC)


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


def _draft() -> ProfileDraft:
    return ProfileDraft(
        display_name="мария",
        birth_date=date(1990, 1, 2),
        birth_time=None,
        birth_time_unknown=True,
        birth_place=None,
        latitude=None,
        longitude=None,
        timezone="Europe/Moscow",
    )


class _SilentModel:
    async def complete_forecast(self, **_kwargs: object) -> object:
        raise AssertionError("the notice planner called the model")


class _Body:
    def __init__(self, name: str, speed: float) -> None:
        self.name = name
        self.speed = speed


class _Ephemeris:
    def __init__(self, flip: datetime) -> None:
        self.flip = flip

    def positions(self, moment: datetime) -> tuple[_Body, ...]:
        speed = -1.0 if moment >= self.flip else 1.0
        return (_Body("меркурий", speed), _Body("венера", 1.0), _Body("марс", 1.0))


class _Sender:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, str]] = []

    async def send_notice(self, telegram_id: int, text: str, page: str) -> None:
        if telegram_id == 8802:
            raise DeliveryBlocked()
        if telegram_id == 8803:
            raise DeliveryRetry(4)
        self.sent.append((telegram_id, text, page))


def _ops(
    factory: async_sessionmaker[AsyncSession],
    ephemeris: _Ephemeris | None = None,
) -> OpsService:
    return OpsService(
        lambda: SqlUnitOfWork(factory),
        load_prompts(ROOT / "resources" / "prompts" / "forecasts.yaml"),
        None,  # type: ignore[arg-type]
        _SilentModel(),  # type: ignore[arg-type]
        ephemeris or _Ephemeris(datetime(2099, 1, 1, tzinfo=UTC)),
        zone_name="Europe/Moscow",
        locale="ru",
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
        clock=lambda: MOMENT,
    )


async def _person(
    factory: async_sessionmaker[AsyncSession],
    telegram_id: int,
    *,
    day: bool = False,
    moon: bool = False,
    retro: bool = False,
) -> object:
    async with SqlUnitOfWork(factory) as uow:
        user = await uow.users.upsert_telegram(telegram_id, "kept", "ru")
        await uow.profiles.upsert(user.id, _draft())
        await uow.notification_settings.save_preferences(
            user.id,
            time(9, 0),
            "Europe/Moscow",
            day=day,
            moon=moon,
            retro=retro,
        )
        await uow.commit()
        return user


@pytest.mark.asyncio
async def test_lease_survives_a_second_claim_until_it_expires(database_url: str) -> None:
    engine, factory = _factory(database_url)
    user = await _person(factory, 8801)
    async with SqlUnitOfWork(factory) as uow:
        await uow.outbox.enqueue(user.id, "day", "bot.day_fallback", MOMENT.date(), MOMENT)
        await uow.commit()
    async with SqlUnitOfWork(factory) as uow:
        claimed = await uow.outbox.claim_due(MOMENT)
        await uow.commit()
    assert len(claimed) == 1
    async with SqlUnitOfWork(factory) as uow:
        assert await uow.outbox.claim_due(MOMENT) == []
        await uow.commit()
    async with factory() as session:
        row = await session.get(NotificationOutboxRow, claimed[0].id)
        assert row is not None
        assert row.status == "reserved"
        assert row.sent_at is None
        row.leased_until = MOMENT - timedelta(minutes=1)
        await session.commit()
    async with SqlUnitOfWork(factory) as uow:
        again = await uow.outbox.claim_due(MOMENT)
        await uow.commit()
    assert [job.id for job in again] == [claimed[0].id]
    async with factory() as session:
        row = await session.get(NotificationOutboxRow, claimed[0].id)
        assert row is not None
        assert row.status == "reserved"
        assert row.sent_at is None
    async with SqlUnitOfWork(factory) as uow:
        await uow.outbox.mark_sent(claimed[0].id, MOMENT)
        await uow.commit()
    async with factory() as session:
        row = await session.get(NotificationOutboxRow, claimed[0].id)
        assert row is not None
        assert row.status == "sent"
        assert row.sent_at == MOMENT
    await engine.dispose()


@pytest.mark.asyncio
async def test_blocked_and_retry_do_not_mark_sent(database_url: str) -> None:
    engine, factory = _factory(database_url)
    blocked = await _person(factory, 8802)
    retry = await _person(factory, 8803)
    async with SqlUnitOfWork(factory) as uow:
        await uow.outbox.enqueue(
            blocked.id,
            "day",
            "bot.day_ready",
            MOMENT.date(),
            MOMENT,
            page="reading/day",
        )
        await uow.outbox.enqueue(
            retry.id,
            "moon",
            "bot.moon_ready",
            MOMENT.date(),
            MOMENT,
            page="reading/moon",
        )
        await uow.commit()
    catalog = load_catalog(ROOT / "resources", "ru", MemoryCache(8))
    service = OutboxService(lambda: SqlUnitOfWork(factory), catalog, SendPace(10_000))
    await service.dispatch_due(_Sender())
    async with factory() as session:
        user = await session.scalar(select(UserRow).where(UserRow.telegram_id == 8802))
        assert user is not None
        assert user.is_blocked is True
        row = await session.scalar(
            select(NotificationOutboxRow).where(NotificationOutboxRow.user_id == blocked.id)
        )
        assert row is not None
        assert row.status == "failed"
        assert row.sent_at is None
    async with factory() as session:
        row = await session.scalar(
            select(NotificationOutboxRow).where(NotificationOutboxRow.user_id == retry.id)
        )
        assert row is not None
        assert row.status == "pending"
        assert row.sent_at is None
        assert row.scheduled_for > MOMENT
    await engine.dispose()


@pytest.mark.asyncio
async def test_planner_reads_cache_and_retro_without_the_model(database_url: str) -> None:
    engine, factory = _factory(database_url)
    user = await _person(factory, 8804, day=True, moon=True, retro=True)
    prompts = load_prompts(ROOT / "resources" / "prompts" / "forecasts.yaml")
    day = local_date(MOMENT, "Europe/Moscow")
    moon_key = forecast_cache_key(
        "moon",
        period_key("moon", MOMENT, "Europe/Moscow"),
        moon_segment(day),
        "",
        "ru",
        prompts.get("moon").version,
    )
    async with SqlUnitOfWork(factory) as uow:
        await uow.forecast_cache.put(
            moon_key,
            None,
            "moon",
            {"title": "луна"},
            MOMENT + timedelta(days=1),
        )
        await uow.subscriptions.add(
            user.id,
            "premium",
            "active",
            MOMENT - timedelta(days=1),
            MOMENT + timedelta(days=20),
            "subscription",
        )
        await uow.commit()
    created = await _ops(factory, _Ephemeris(datetime(2026, 6, 18, tzinfo=UTC))).plan()
    assert created == 3
    async with factory() as session:
        rows = list(
            (
                await session.execute(
                    select(NotificationOutboxRow).where(NotificationOutboxRow.user_id == user.id)
                )
            ).scalars()
        )
    by_kind = {row.kind: row for row in rows}
    assert by_kind["day"].payload["text_key"] == "bot.day_fallback"
    assert by_kind["moon"].payload["text_key"] == "bot.moon_ready"
    assert by_kind["retro"].payload["text_key"] == "bot.retro_preview"
    assert by_kind["retro"].payload["planet"] == "меркурий"
    assert by_kind["retro"].event_key.startswith("меркурий:2026-06-18:preview")
    assert await _ops(factory, _Ephemeris(datetime(2026, 6, 18, tzinfo=UTC))).plan() == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_referral_rejects_self_and_a_second_attribution(database_url: str) -> None:
    engine, factory = _factory(database_url)
    async with SqlUnitOfWork(factory) as uow:
        owner = await uow.users.upsert_telegram(8805, None, "ru")
        friend = await uow.users.upsert_telegram(8806, None, "ru")
        code = await uow.users.ensure_referral_code(owner.id)
        assert await uow.users.bind_referrer(owner.id, f"ref_{code}") is False
        assert await uow.users.bind_referrer(friend.id, "plain") is False
        assert await uow.users.bind_referrer(friend.id, f"ref_{code}") is True
        assert await uow.users.bind_referrer(friend.id, f"ref_{code}") is False
        await uow.profiles.upsert(friend.id, _draft())
        assert await uow.profiles.touch_streak(friend.id, date(2026, 6, 1)) == 1
        assert await uow.profiles.touch_streak(friend.id, date(2026, 6, 1)) == 1
        assert await uow.profiles.touch_streak(friend.id, date(2026, 6, 2)) == 2
        assert await uow.profiles.touch_streak(friend.id, date(2026, 6, 4)) == 1
        await uow.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_overview_hides_people_and_delete_keeps_a_thin_charge(
    database_url: str,
    tmp_path: Path,
) -> None:
    engine, factory = _factory(database_url)
    async with SqlUnitOfWork(factory) as uow:
        user = await uow.users.upsert_telegram(8807, "secret-name", "ru")
        await uow.profiles.upsert(user.id, _draft())
        history = await uow.forecast_history.add(
            user.id,
            "day",
            date(2026, 6, 15),
            {"title": "день", "prompt_version": "2"},
        )
        await uow.feedback.add(user.id, history, 4, "личный комментарий")
        order = await uow.orders.add(user.id, "premium", 250, "XTR", "paid", "payload-ops")
        charge = await uow.charges.add(
            order.id,
            user.id,
            "charge-ops",
            250,
            "XTR",
            MOMENT,
            MOMENT,
            MOMENT,
            {"currency": "XTR", "birth_place": "казань", "display_name": "мария"},
        )
        await uow.commit()
        user_id = user.id
        order_id = order.id
        charge_id = charge.id
    async with factory() as session:
        stored = await session.get(OrderRow, order_id)
        assert stored is not None
        stored.invoice_link = "https://t.me/invoice/secret"
        await session.commit()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>starflow</title>", encoding="utf-8")
    settings = make_settings(
        database_url=database_url,
        singleton_lock=False,
        frontend_dist=dist,
        logo_path=ROOT / "static" / "logo.png",
        bot_retry_sec=30,
    )
    container = build_container(settings)
    app = build_fastapi(container)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            guest = _init_data(
                settings.bot_token,
                {"id": 2, "username": "guest"},
                int(unix_clock.time()),
            )
            admin = _init_data(
                settings.bot_token,
                {"id": 1, "username": "admin"},
                int(unix_clock.time()),
            )
            intent = {"X-Starflow-Request": "1"}
            opened = await client.post(
                "/api/v1/session",
                headers={"Authorization": f"TMA {guest}", **intent},
            )
            assert opened.status_code == 200
            denied = await client.get("/api/v1/admin/overview")
            assert denied.status_code == 403
            hidden = await client.get("/api/v1/admin/users")
            assert hidden.status_code == 403
            grant = await client.post(
                "/api/v1/billing/admin-grants",
                headers=intent,
                json={"user_id": str(user_id), "days": 3, "reason": "нет", "confirm": True},
            )
            assert grant.status_code == 403
            await client.post("/api/v1/session/logout", headers=intent)
            opened_admin = await client.post(
                "/api/v1/session",
                headers={"Authorization": f"TMA {admin}", **intent},
            )
            assert opened_admin.status_code == 200
            overview = await client.get(
                "/api/v1/admin/overview",
                params={"start": "2026-10-01", "end": "2026-10-27"},
            )
            assert overview.status_code == 200
            body = overview.json()
            assert "display_name" not in body
            assert "birth_date" not in body
            assert "username" not in body
            assert "content" not in body
            assert body["definitions"]["active_users"]
            assert any(
                item["forecast_type"] == "day" and item["prompt_version"] == "2"
                for item in body["feedback"]
            )
            assert "личный" not in overview.text
            people = await client.get("/api/v1/admin/users")
            assert people.status_code == 200
            listed = people.json()["users"]
            person = next(item for item in listed if item["user_id"] == str(user_id))
            assert person == {
                "user_id": str(user_id),
                "telegram_id": 8807,
                "username": "secret-name",
                "display_name": "мария",
                "premium": False,
            }
            assert "1990" not in people.text
            assert "личный" not in people.text
            wide = await client.get(
                "/api/v1/admin/overview",
                params={"start": "2020-01-01", "end": "2026-06-20"},
            )
            assert wide.status_code == 422
    finally:
        await container.shutdown()
    async with SqlUnitOfWork(factory) as uow:
        await uow.users.delete(user_id)
        await uow.commit()
    async with factory() as session:
        assert await session.get(UserRow, user_id) is None
        kept = await session.get(PaymentChargeRow, charge_id)
        assert kept is not None
        assert kept.user_id is None
        assert kept.telegram_payment_charge_id == "charge-ops"
        assert kept.provider_payload == {"currency": "XTR", "amount_stars": 250}
        order_row = await session.get(OrderRow, order_id)
        assert order_row is not None
        assert order_row.user_id is None
        assert order_row.invoice_link is None
    await engine.dispose()
