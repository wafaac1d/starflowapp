from datetime import datetime, timedelta
from uuid import UUID

from starflow.domain.broadcast import BroadcastJob, audience_ok, broadcast_text_ok
from starflow.domain.codes import BalanceCode, code_name_ok
from starflow.domain.entitlement import Grant
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.stars import settle_spend
from starflow.domain.time import now_utc
from starflow.services.ops import OpsService
from starflow.services.wallet import StarsWallet

USER = UUID("00000000-0000-0000-0000-000000000041")
KEY = "premiumkey01"


class _Billing:
    def __init__(self, balance: int, grants: list[Grant] | None = None) -> None:
        self.balance = balance
        self.rows = list(grants or [])
        self.spends: set[tuple[str, str]] = set()

    async def owns_spend(self, user_id: UUID, feature: str, subject: str) -> bool:
        return (feature, subject) in self.spends

    async def star_balance(self, user_id: UUID) -> int:
        return self.balance

    async def spend_stars(self, user_id: UUID, feature: str, subject: str, price: int):
        already = (feature, subject) in self.spends
        settled = settle_spend(self.balance, price, already)
        if settled.charged:
            self.balance = settled.balance
            self.spends.add((feature, subject))
        return settled

    async def grants(self, user_id: UUID) -> tuple[Grant, ...]:
        return tuple(self.rows)

    async def insert_grant(
        self,
        user_id: UUID,
        source: str,
        start: datetime,
        end: datetime,
        **kwargs: object,
    ) -> UUID:
        grant = Grant(
            id=UUID(int=len(self.rows) + 1),
            user_id=user_id,
            source=source,
            status="active",
            period_start=start,
            period_end=end,
            grace_until=None,
            revoked_at=None,
        )
        self.rows.append(grant)
        return grant.id

    async def add_event(self, *args: object, **kwargs: object) -> None:
        return None


class _Work:
    def __init__(self, billing: _Billing) -> None:
        self.billing = billing

    async def __aenter__(self) -> "_Work":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None


def test_code_and_audience_rules() -> None:
    assert code_name_ok("Лето-1") is True
    assert code_name_ok("ab") is False
    assert code_name_ok("gift code") is False
    assert audience_ok("inactive") is True
    assert audience_ok("friends") is False
    assert broadcast_text_ok("  ") is False
    assert broadcast_text_ok("x" * 500) is True
    assert broadcast_text_ok("x" * 501) is False


async def test_premium_from_balance_extends_and_does_not_repeat() -> None:
    end = now_utc() + timedelta(days=10)
    billing = _Billing(
        250,
        [
            Grant(
                id=UUID(int=9),
                user_id=USER,
                source="subscription",
                status="active",
                period_start=end - timedelta(days=30),
                period_end=end,
                grace_until=None,
                revoked_at=None,
            )
        ],
    )
    wallet = StarsWallet(lambda: _Work(billing))
    bought = await wallet.buy_premium(USER, KEY, 250, 30)
    assert bought.charged is True
    assert bought.balance == 0
    added = billing.rows[-1]
    assert added.source == "balance"
    assert added.period_start == end
    assert added.period_end == end + timedelta(days=30)
    again = await wallet.buy_premium(USER, KEY, 250, 30)
    assert again.charged is False
    assert len(billing.rows) == 2


async def test_premium_from_balance_refuses_a_short_balance() -> None:
    billing = _Billing(40)
    wallet = StarsWallet(lambda: _Work(billing))
    try:
        await wallet.buy_premium(USER, KEY, 250, 30)
    except FieldInvalid as error:
        assert error.message_key == "errors.stars_required"
    else:
        raise AssertionError("short balance must not buy premium")
    assert billing.rows == []
    assert billing.balance == 40


class _Codes(_Billing):
    def __init__(self, expires) -> None:
        super().__init__(0)
        self.code = BalanceCode(
            id=UUID(int=3),
            code="Лето-1",
            stars=40,
            max_uses=1,
            used_count=0,
            expires_at=expires,
        )
        self.redeemed = False

    async def lock_balance_code(self, name: str) -> BalanceCode | None:
        if name.casefold() != self.code.code.casefold():
            return None
        return self.code

    async def has_balance_redemption(self, code_id: UUID, user_id: UUID) -> bool:
        return self.redeemed

    async def add_balance_redemption(self, code_id: UUID, user_id: UUID, now: datetime) -> None:
        if self.redeemed:
            raise Conflict("dup")
        self.redeemed = True

    async def consume_balance_code(self, code_id: UUID) -> bool:
        return True

    async def credit_stars(self, user_id: UUID, amount: int) -> int:
        self.balance += amount
        return self.balance


async def test_balance_code_credits_once() -> None:
    billing = _Codes(now_utc() + timedelta(days=2))
    wallet = StarsWallet(lambda: _Work(billing))
    assert await wallet.redeem_code(USER, "лето-1") == 40
    try:
        await wallet.redeem_code(USER, "Лето-1")
    except FieldInvalid as error:
        assert error.message_key == "errors.gift_invalid"
    else:
        raise AssertionError("the same code must not credit twice")
    assert billing.balance == 40


async def test_broadcast_fills_a_batch_and_then_finishes() -> None:
    person = UUID(int=7)
    sent: list[str] = []

    class _Ops:
        def __init__(self) -> None:
            self.targets: list[UUID] = []
            self.finished = False

        async def next_queued_broadcast(self) -> BroadcastJob | None:
            if self.finished:
                return None
            return BroadcastJob(id=UUID(int=4), body="Тихий вечер", audience="all")

        async def broadcast_user_ids(
            self,
            audience: str,
            broadcast_id: UUID,
            now: datetime,
            limit: int = 25,
        ) -> list[UUID]:
            if person in self.targets:
                return []
            return [person]

        async def finish_broadcast(self, broadcast_id: UUID, now: datetime) -> None:
            self.finished = True

        async def remember_broadcast_target(self, broadcast_id: UUID, user_id: UUID) -> None:
            self.targets.append(user_id)

    class _Outbox:
        async def enqueue(
            self,
            user_id: UUID,
            kind: str,
            text_key: str,
            local_date: datetime,
            scheduled_for: datetime,
            event_key: str | None = None,
            page: str = "",
            planet: str = "",
            body: str = "",
        ) -> UUID:
            sent.append(body)
            return user_id

    class _Box:
        def __init__(self, ops: _Ops, outbox: _Outbox) -> None:
            self.ops = ops
            self.outbox = outbox

        async def __aenter__(self) -> "_Box":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def commit(self) -> None:
            return None

    ops = _Ops()
    outbox = _Outbox()
    service = OpsService(
        lambda: _Box(ops, outbox),
        object(),
        object(),
        object(),
        object(),
        zone_name="Europe/Moscow",
        locale="ru",
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
    )
    assert await service.fill_broadcasts() == 1
    assert sent == ["Тихий вечер"]
    assert await service.fill_broadcasts() == 0
    assert ops.finished is True
