from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import F, Router
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
    TelegramObject,
    WebAppInfo,
)

from starflow.bot.screens import SCREENS, screen_url
from starflow.i18n.catalog import Catalog
from starflow.services.billing import BillingService
from starflow.services.session import SessionService


class UpdateContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        update = data.get("event_update")
        update_id = getattr(update, "update_id", None)
        if isinstance(update_id, int):
            structlog.contextvars.bind_contextvars(update_id=update_id)
        try:
            return await handler(event, data)
        finally:
            structlog.contextvars.unbind_contextvars("update_id", "user_id")


def register_handlers(
    router: Router,
    session_service: SessionService,
    catalog: Catalog,
    mini_app_url: str,
    billing: BillingService,
) -> None:
    @router.pre_checkout_query()
    async def on_pre_checkout(query: PreCheckoutQuery) -> None:
        await billing.pre_checkout(
            query.id,
            query.from_user.id,
            query.currency,
            query.total_amount,
            query.invoice_payload,
        )

    @router.message(F.successful_payment)
    async def on_paid(message: Message) -> None:
        payment = message.successful_payment
        user = message.from_user
        if payment is None or user is None:
            return
        structlog.contextvars.bind_contextvars(user_id=user.id)
        await billing.apply_payment(
            telegram_user_id=user.id,
            currency=payment.currency,
            total_amount=payment.total_amount,
            invoice_payload=payment.invoice_payload,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            provider_payment_charge_id=payment.provider_payment_charge_id,
            is_recurring=bool(payment.is_recurring),
            is_first_recurring=bool(payment.is_first_recurring),
            subscription_expiration_date=payment.subscription_expiration_date,
        )

    @router.message(CommandStart())
    async def on_start(message: Message, command: CommandObject) -> None:
        user = message.from_user
        if user is None:
            await message.answer(catalog.text("bot.start_missing_user"))
            return
        structlog.contextvars.bind_contextvars(user_id=user.id)
        await session_service.accept_telegram_user(
            user.id,
            user.username,
            user.language_code,
            command.args,
        )
        await _open(message, catalog, mini_app_url, "", "bot.start", "bot.start_without_app")

    for screen in SCREENS:
        _register_screen(router, catalog, mini_app_url, screen)

    @router.message(Command("delete_me"))
    async def on_delete(message: Message) -> None:
        user = message.from_user
        if user is not None:
            structlog.contextvars.bind_contextvars(user_id=user.id)
        button = InlineKeyboardButton(
            text=catalog.text("bot.delete_confirm"),
            callback_data="delete_me",
        )
        await message.answer(
            catalog.text("bot.delete_ask"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
        )

    @router.message(F.text)
    async def on_text(message: Message) -> None:
        user = message.from_user
        if user is None:
            await message.answer(catalog.text("bot.start_missing_user"))
            return
        structlog.contextvars.bind_contextvars(user_id=user.id)
        await _open(message, catalog, mini_app_url, "", "bot.start", "bot.start_without_app")

    @router.callback_query(F.data == "delete_me")
    async def on_delete_confirmed(query: CallbackQuery) -> None:
        user = query.from_user
        structlog.contextvars.bind_contextvars(user_id=user.id)
        removed = await session_service.delete_telegram_account(user.id)
        text = catalog.text("bot.delete_done" if removed else "bot.delete_missing")
        await query.answer()
        if query.message is not None:
            await query.message.answer(text)


def _register_screen(router: Router, catalog: Catalog, mini_app_url: str, screen: str) -> None:
    @router.message(Command(screen))
    async def on_screen(message: Message) -> None:
        user = message.from_user
        if user is not None:
            structlog.contextvars.bind_contextvars(user_id=user.id)
        await _open(
            message,
            catalog,
            mini_app_url,
            screen,
            f"bot.{screen}",
            "bot.start_without_app",
        )


async def _open(
    message: Message,
    catalog: Catalog,
    mini_app_url: str,
    screen: str,
    text_key: str,
    missing_key: str,
) -> None:
    if not mini_app_url:
        await message.answer(catalog.text(missing_key))
        return
    url = mini_app_url if not screen else screen_url(mini_app_url, screen)
    button = InlineKeyboardButton(text=catalog.text("bot.open"), web_app=WebAppInfo(url=url))
    await message.answer(
        catalog.text(text_key),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )
