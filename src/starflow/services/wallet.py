"""Списание баланса. Пополнение приходит только из подтверждённого платежа."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.errors import FieldInvalid
from starflow.domain.stars import SpendResult, price_of, subject_ok
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
