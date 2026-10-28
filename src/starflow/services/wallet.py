"""Списание баланса. Пополнение приходит только из подтверждённого платежа."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.codes import code_days_ok, code_name_ok, code_uses_ok
from starflow.domain.entitlement import access_end
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.quota import idempotency_key_ok
from starflow.domain.stars import SpendResult, price_of, subject_ok, topup_amount_ok
from starflow.domain.time import now_utc
from starflow.repositories.billing import BillingRepository


class WalletStore(Protocol):
    billing: BillingRepository

    async def commit(self) -> None: ...


class WalletWork(Protocol):
    async def __aenter__(self) -> WalletStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class PremiumPurchase:
    balance: int
    charged: bool


class StarsWallet:
    def __init__(self, uow_factory: Callable[[], WalletWork]) -> None:
        self._uow_factory = uow_factory

    async def balance(self, user_id: UUID) -> int:
        async with self._uow_factory() as uow:
            return await uow.billing.star_balance(user_id)

    async def owns(self, user_id: UUID, feature: str, subject: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.billing.owns_spend(user_id, feature, subject)

    async def can_pay(self, user_id: UUID, feature: str, subject: str) -> bool:
        if await self.owns(user_id, feature, subject):
            return True
        try:
            price = price_of(feature)
        except ValueError:
            return False
        return await self.balance(user_id) >= price

    async def buy(self, user_id: UUID, feature: str, subject: str) -> SpendResult:
        try:
            price = price_of(feature)
        except ValueError as error:
            raise FieldInvalid("feature", "errors.validation") from error
        if not subject_ok(subject):
            raise FieldInvalid("subject", "errors.validation")
        async with self._uow_factory() as uow:
            result = await uow.billing.spend_stars(user_id, feature, subject, price)
            await uow.commit()
            return result

    async def buy_premium(self, user_id: UUID, key: str, price: int, days: int) -> PremiumPurchase:
        if not idempotency_key_ok(key) or price < 1 or days < 1:
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        now = now_utc()
        async with self._uow_factory() as uow:
            if await uow.billing.owns_spend(user_id, "premium", key):
                balance = await uow.billing.star_balance(user_id)
                await uow.commit()
                return PremiumPurchase(balance=balance, charged=False)
            result = await uow.billing.spend_stars(user_id, "premium", key, price)
            if not result.allowed:
                await uow.commit()
                raise FieldInvalid("stars", "errors.stars_required")
            grants = await uow.billing.grants(user_id)
            open_end = access_end(grants, now)
            start = open_end if open_end is not None and open_end > now else now
            grant_id = await uow.billing.insert_grant(
                user_id,
                "balance",
                start,
                start + timedelta(days=days),
            )
            await uow.billing.add_event(
                grant_id,
                user_id,
                "balance_premium",
                {"days": days, "price": price},
            )
            await uow.commit()
            return PremiumPurchase(balance=result.balance, charged=True)

    async def create_code(
        self,
        *,
        actor_is_admin: bool,
        name: str,
        stars: int,
        uses: int,
        days: int,
    ) -> str:
        if not actor_is_admin:
            raise FieldInvalid("admin", "errors.unauthorized")
        cleaned = name.strip()
        if not code_name_ok(cleaned) or not topup_amount_ok(stars):
            raise FieldInvalid("code", "errors.validation")
        if not code_uses_ok(uses) or not code_days_ok(days):
            raise FieldInvalid("code", "errors.validation")
        expires_at = now_utc() + timedelta(days=days)
        async with self._uow_factory() as uow:
            try:
                created = await uow.billing.insert_balance_code(cleaned, stars, uses, expires_at)
            except Conflict as error:
                raise FieldInvalid("code", "errors.conflict") from error
            await uow.commit()
        return created.code

    async def redeem_code(self, user_id: UUID, name: str) -> int:
        cleaned = name.strip()
        if not code_name_ok(cleaned):
            raise FieldInvalid("code", "errors.gift_invalid")
        now = now_utc()
        async with self._uow_factory() as uow:
            found = await uow.billing.lock_balance_code(cleaned)
            if found is None or found.expires_at <= now or found.used_count >= found.max_uses:
                raise FieldInvalid("code", "errors.gift_invalid")
            if await uow.billing.has_balance_redemption(found.id, user_id):
                raise FieldInvalid("code", "errors.gift_invalid")
            try:
                await uow.billing.add_balance_redemption(found.id, user_id, now)
            except Conflict as error:
                raise FieldInvalid("code", "errors.gift_invalid") from error
            consumed = await uow.billing.consume_balance_code(found.id)
            if not consumed:
                raise FieldInvalid("code", "errors.gift_invalid")
            balance = await uow.billing.credit_stars(user_id, found.stars)
            await uow.commit()
            return balance
