"""Порт Telegram Stars. Реализация живёт у бота, тесты подставляют свою."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InvoiceDraft:
    title: str
    description: str
    payload: str
    amount: int
    label: str
    subscription_period: int | None


class StarGateway(Protocol):
    async def create_invoice_link(self, draft: InvoiceDraft) -> str: ...

    async def answer_pre_checkout(
        self,
        query_id: str,
        ok: bool,
        error_message: str | None,
    ) -> None: ...

    async def edit_user_star_subscription(
        self,
        user_id: int,
        telegram_payment_charge_id: str,
        is_canceled: bool,
    ) -> None: ...

    async def refund_star_payment(self, user_id: int, telegram_payment_charge_id: str) -> None: ...
