"""Вызовы Bot API для Stars. Пустой provider_token — по текущей странице метода."""

from aiogram import Bot
from aiogram.types import LabeledPrice

from starflow.domain.billing import MAX_STARS, SUBSCRIPTION_PERIOD_SEC
from starflow.services.stars import InvoiceDraft


class AiogramStarGateway:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def create_invoice_link(self, draft: InvoiceDraft) -> str:
        if draft.amount < 1 or draft.amount > MAX_STARS:
            raise ValueError("star price is outside 1..10000")
        if draft.subscription_period not in (None, SUBSCRIPTION_PERIOD_SEC):
            raise ValueError("subscription_period must be 2592000 or omitted")
        if not 1 <= len(draft.title) <= 32 or not 1 <= len(draft.description) <= 255:
            raise ValueError("invoice title or description is outside the telegram limit")
        if not 1 <= len(draft.payload.encode()) <= 128:
            raise ValueError("invoice payload is outside 1..128 bytes")
        prices = [LabeledPrice(label=draft.label, amount=draft.amount)]
        if draft.subscription_period is None:
            return await self._bot.create_invoice_link(
                title=draft.title,
                description=draft.description,
                payload=draft.payload,
                currency="XTR",
                prices=prices,
                provider_token="",
            )
        return await self._bot.create_invoice_link(
            title=draft.title,
            description=draft.description,
            payload=draft.payload,
            currency="XTR",
            prices=prices,
            provider_token="",
            subscription_period=draft.subscription_period,
        )

    async def answer_pre_checkout(
        self,
        query_id: str,
        ok: bool,
        error_message: str | None,
    ) -> None:
        await self._bot.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=ok,
            error_message=error_message,
        )

    async def edit_user_star_subscription(
        self,
        user_id: int,
        telegram_payment_charge_id: str,
        is_canceled: bool,
    ) -> None:
        await self._bot.edit_user_star_subscription(
            user_id=user_id,
            telegram_payment_charge_id=telegram_payment_charge_id,
            is_canceled=is_canceled,
        )

    async def refund_star_payment(self, user_id: int, telegram_payment_charge_id: str) -> None:
        await self._bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=telegram_payment_charge_id,
        )
