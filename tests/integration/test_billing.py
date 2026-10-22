"""Stars без живого Telegram: шлюз подменён, доступ даёт только charge."""

import asyncio
import itertools
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from starflow.cache.memory import MemoryCache
from starflow.db.engine import create_session_factory
from starflow.db.tables import NotificationOutboxRow, SubscriptionRow
from starflow.domain.errors import FieldInvalid, PaymentUnavailable
from starflow.domain.plans import load_plans
from starflow.i18n.catalog import load_catalog
from starflow.repositories.uow import SqlUnitOfWork
from starflow.services.billing import BillingService
from starflow.services.stars import InvoiceDraft

ROOT = Path(__file__).resolve().parents[2]
_TELEGRAM_IDS = itertools.count(3100)


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


class FakeStars:
    def __init__(self) -> None:
        self.drafts: list[InvoiceDraft] = []
        self.answers: list[tuple[str, bool, str | None]] = []
        self.edits: list[tuple[int, str, bool]] = []
        self.refunds: list[tuple[int, str]] = []
        self.fail_edit = False
        self.delay = 0.0

    async def create_invoice_link(self, draft: InvoiceDraft) -> str:
        if self.delay:
            await asyncio.sleep(self.delay)
        if draft.subscription_period not in (None, 2592000):
            raise AssertionError(draft.subscription_period)
        if draft.amount != 250:
            raise AssertionError(draft.amount)
        self.drafts.append(draft)
        return f"https://t.me/invoice/{len(self.drafts)}"

    async def answer_pre_checkout(
        self,
        query_id: str,
        ok: bool,
        error_message: str | None,
    ) -> None:
        self.answers.append((query_id, ok, error_message))

    async def edit_user_star_subscription(
        self,
        user_id: int,
        telegram_payment_charge_id: str,
        is_canceled: bool,
    ) -> None:
        if self.fail_edit:
            raise RuntimeError("telegram")
        self.edits.append((user_id, telegram_payment_charge_id, is_canceled))

    async def refund_star_payment(self, user_id: int, telegram_payment_charge_id: str) -> None:
        self.refunds.append((user_id, telegram_payment_charge_id))


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    raise RuntimeError(f"unsupported database url {url}")


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


@pytest.fixture
async def factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _service(
    factory: async_sessionmaker[AsyncSession],
    gateway: FakeStars,
    clock: Clock,
) -> BillingService:
    return BillingService(
        lambda: SqlUnitOfWork(factory),
        gateway,
        load_plans(ROOT / "resources" / "plans.yaml"),
        "p" * 32,
        load_catalog(ROOT / "resources", "ru", MemoryCache(4)),
        "https://app.example",
        now=clock,
    )


async def _user(factory: async_sessionmaker[AsyncSession], referrer: int | None = None):
    async with SqlUnitOfWork(factory) as uow:
        created = await uow.users.upsert_telegram(next(_TELEGRAM_IDS), None, "ru")
        if referrer is not None:
            code = await uow.users.ensure_referral_code(created.id)
            friend = await uow.users.upsert_telegram(referrer, None, "ru")
            await uow.users.bind_referrer(friend.id, f"ref_{code}")
            await uow.commit()
            return created, friend
        await uow.commit()
        return created


async def _count(
    factory: async_sessionmaker[AsyncSession],
    user_id: object,
    source: str,
) -> int:
    async with factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(SubscriptionRow)
            .where(SubscriptionRow.user_id == user_id, SubscriptionRow.source == source)
        )
        return int(result.scalar_one())


async def _pay(
    service: BillingService,
    telegram_id: int,
    payload: str,
    charge_id: str,
    *,
    expiration: int | None = None,
    recurring: bool = True,
    first: bool = True,
) -> None:
    await service.apply_payment(
        telegram_user_id=telegram_id,
        currency="XTR",
        total_amount=250,
        invoice_payload=payload,
        telegram_payment_charge_id=charge_id,
        provider_payment_charge_id="provider",
        is_recurring=recurring,
        is_first_recurring=first,
        subscription_expiration_date=expiration,
    )


@pytest.mark.asyncio
async def test_checkout_payment_and_ignored_client_status(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = Clock(datetime(2026, 10, 21, 12, tzinfo=UTC))
    gateway = FakeStars()
    service = _service(factory, gateway, clock)
    user = await _user(factory)
    view = await service.create_invoice(user.id, "subscription", "idem-sub-001")
    payload = gateway.drafts[-1].payload
    assert gateway.drafts[-1].subscription_period == 2592000
    assert view.subscription_invoice_link is not None
    assert view.subscription_order_id is not None
    await service.pre_checkout("ok", user.telegram_id, "XTR", 250, payload)
    await service.pre_checkout("amount", user.telegram_id, "XTR", 1, payload)
    await service.pre_checkout("user", user.telegram_id + 50, "XTR", 250, payload)
    await service.pre_checkout("currency", user.telegram_id, "USD", 250, payload)
    flipped = payload[:-1] + ("0" if payload[-1] != "0" else "1")
    await service.pre_checkout("sign", user.telegram_id, "XTR", 250, flipped)
    assert [item[1] for item in gateway.answers] == [True, False, False, False, False]
    noted = await service.note_client_status(user.id, view.subscription_order_id, "paid")
    assert noted.premium is False
    assert noted.subscription_payment_state == "pending"
    end = clock.moment + timedelta(days=30)
    await _pay(service, user.telegram_id, payload, "charge-1", expiration=int(end.timestamp()))
    paid = await service.view(user.id)
    assert paid.premium is True
    assert paid.subscription_payment_state == "success"
    await _pay(service, user.telegram_id, payload, "charge-1", expiration=int(end.timestamp()))
    assert await _count(factory, user.id, "subscription") == 1
    later = end + timedelta(days=30)
    await _pay(
        service,
        user.telegram_id,
        payload,
        "charge-2",
        expiration=int(later.timestamp()),
        first=False,
    )
    assert await _count(factory, user.id, "subscription") == 2
    renewed = await service.view(user.id)
    assert renewed.access_until == later
    await service.set_canceled(user.id, True)
    assert gateway.edits[-1] == (user.telegram_id, "charge-1", True)
    cancelled = await service.view(user.id)
    assert cancelled.premium is True
    assert cancelled.subscription_state == "cancel_scheduled"
    await service.set_canceled(user.id, False)
    assert gateway.edits[-1] == (user.telegram_id, "charge-1", False)


@pytest.mark.asyncio
async def test_parallel_creates_one_invoice(factory: async_sessionmaker[AsyncSession]) -> None:
    gateway = FakeStars()
    gateway.delay = 0.2
    service = _service(factory, gateway, Clock(datetime(2026, 10, 21, 12, tzinfo=UTC)))
    user = await _user(factory)
    await asyncio.gather(
        service.create_invoice(user.id, "subscription", "idem-par-0001"),
        service.create_invoice(user.id, "subscription", "idem-par-0002"),
    )
    assert len(gateway.drafts) == 1


@pytest.mark.asyncio
async def test_cancel_retry_grace_and_reminder(factory: async_sessionmaker[AsyncSession]) -> None:
    clock = Clock(datetime(2026, 10, 21, 12, tzinfo=UTC))
    gateway = FakeStars()
    service = _service(factory, gateway, clock)
    user = await _user(factory)
    await service.create_invoice(user.id, "subscription", "idem-grace-01")
    payload = gateway.drafts[-1].payload
    end = clock.moment + timedelta(days=2)
    await _pay(service, user.telegram_id, payload, "charge-grace", expiration=int(end.timestamp()))
    gateway.fail_edit = True
    with pytest.raises(PaymentUnavailable):
        await service.set_canceled(user.id, True)
    assert (await service.view(user.id)).subscription_state == "active"
    gateway.fail_edit = False
    await service.maintain()
    assert (await service.view(user.id)).subscription_state == "cancel_scheduled"
    await service.maintain()
    async with factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(NotificationOutboxRow)
            .where(
                NotificationOutboxRow.user_id == user.id,
                NotificationOutboxRow.kind == "subscription_ending",
            )
        )
        assert int(result.scalar_one()) == 1
    clock.moment = end + timedelta(minutes=1)
    await service.maintain()
    assert (await service.view(user.id)).premium is False


@pytest.mark.asyncio
async def test_recurring_grace_hour(factory: async_sessionmaker[AsyncSession]) -> None:
    clock = Clock(datetime(2026, 10, 21, 12, tzinfo=UTC))
    gateway = FakeStars()
    service = _service(factory, gateway, clock)
    user = await _user(factory)
    await service.create_invoice(user.id, "subscription", "idem-delay-01")
    payload = gateway.drafts[-1].payload
    stale = clock.moment - timedelta(minutes=30)
    await _pay(
        service, user.telegram_id, payload, "charge-delay", expiration=int(stale.timestamp())
    )
    assert (await service.view(user.id)).premium is False
    await service.maintain()
    assert (await service.view(user.id)).premium is True
    clock.moment = stale + timedelta(hours=2)
    await service.maintain()
    assert (await service.view(user.id)).premium is False


@pytest.mark.asyncio
async def test_trial_gift_refund_and_referral(factory: async_sessionmaker[AsyncSession]) -> None:
    clock = Clock(datetime(2026, 10, 21, 12, tzinfo=UTC))
    gateway = FakeStars()
    service = _service(factory, gateway, clock)
    referrer = await _user(factory)
    async with SqlUnitOfWork(factory) as uow:
        code = await uow.users.ensure_referral_code(referrer.id)
        buyer = await uow.users.upsert_telegram(next(_TELEGRAM_IDS), None, "ru")
        await uow.users.bind_referrer(buyer.id, f"ref_{code}")
        await uow.commit()
    await service.create_invoice(buyer.id, "subscription", "idem-buyer-01")
    payload = gateway.drafts[-1].payload
    end = clock.moment + timedelta(days=30)
    await _pay(service, buyer.telegram_id, payload, "charge-buyer", expiration=int(end.timestamp()))
    await _pay(
        service,
        buyer.telegram_id,
        payload,
        "charge-buyer-2",
        expiration=int((end + timedelta(days=30)).timestamp()),
        first=False,
    )
    assert await _count(factory, referrer.id, "referral") == 1
    friend = await _user(factory)
    other = await _user(factory)
    await service.create_invoice(buyer.id, "gift", "idem-gift-0001")
    gift_payload = gateway.drafts[-1].payload
    assert gateway.drafts[-1].subscription_period is None
    await _pay(
        service, buyer.telegram_id, gift_payload, "charge-gift", recurring=False, first=False
    )
    await service.pre_checkout("gift-again", buyer.telegram_id, "XTR", 250, gift_payload)
    assert gateway.answers[-1][1] is False
    gift = await service.view(buyer.id)
    assert gift.gift_code is not None
    assert gift.premium is True
    with pytest.raises(FieldInvalid) as denied:
        await service.redeem(buyer.id, gift.gift_code)
    assert denied.value.message_key == "errors.gift_self"

    async def redeem(user_id: object) -> bool:
        try:
            await service.redeem(user_id, gift.gift_code or "")
            return True
        except FieldInvalid:
            return False

    won = await asyncio.gather(redeem(friend.id), redeem(other.id))
    assert won.count(True) == 1
    holder = friend if won[0] else other
    assert await _count(factory, holder.id, "gift") == 1
    attacker = await _user(factory)
    await service.create_invoice(buyer.id, "gift", "idem-gift-0002")
    second_payload = gateway.drafts[-1].payload
    await _pay(
        service,
        buyer.telegram_id,
        second_payload,
        "charge-gift-2",
        recurring=False,
        first=False,
    )
    second = await service.view(buyer.id)
    assert second.gift_code is not None
    for index in range(8):
        with pytest.raises(FieldInvalid):
            await service.redeem(attacker.id, f"not-a-real-code-{index}")
    with pytest.raises(FieldInvalid):
        await service.redeem(attacker.id, second.gift_code)
    lucky = await _user(factory)
    assert (await service.redeem(lucky.id, second.gift_code)).premium is True
    trial_user = await _user(factory)
    opened = await service.start_trial(trial_user.id)
    assert opened.premium is True
    with pytest.raises(FieldInvalid):
        await service.start_trial(trial_user.id)
    await service.grant_admin(
        actor_is_admin=True,
        user_id=buyer.id,
        days=5,
        reason="проверка",
        confirm=True,
    )
    with pytest.raises(FieldInvalid):
        await service.refund(
            actor_is_admin=False,
            charge_id="charge-buyer",
            confirm=True,
            reason="нет",
        )
    await service.refund(
        actor_is_admin=True,
        charge_id="charge-buyer",
        confirm=True,
        reason="возврат проверки",
    )
    assert gateway.refunds == [(buyer.telegram_id, "charge-buyer")]
    async with factory() as session:
        result = await session.execute(
            select(SubscriptionRow).where(SubscriptionRow.user_id == buyer.id)
        )
        loaded = list(result.scalars())
        subscription = [row.status for row in loaded if row.source == "subscription"]
        admin = [row.status for row in loaded if row.source == "admin"]
    assert "revoked" in subscription
    assert "active" in subscription
    assert admin == ["active"]
    assert await _count(factory, referrer.id, "referral") == 1
