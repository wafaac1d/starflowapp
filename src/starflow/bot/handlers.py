from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time, timedelta
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
from starflow.domain.errors import FieldInvalid
from starflow.domain.time import now_utc
from starflow.i18n.catalog import Catalog
from starflow.services.billing import BillingService
from starflow.services.ops import OpsService
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
    ops: OpsService,
    admins: frozenset[int],
) -> None:
    pending_refund: dict[int, tuple[str, str]] = {}

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

    @router.message(Command("stats"))
    async def on_stats(message: Message) -> None:
        await _stats(message, catalog, ops, admins, False)

    @router.message(Command("cache_stats"))
    async def on_cache_stats(message: Message) -> None:
        await _stats(message, catalog, ops, admins, True)

    @router.message(Command("refund"))
    async def on_refund(message: Message, command: CommandObject) -> None:
        user = message.from_user
        if user is None or user.id not in admins:
            await message.answer(catalog.text("bot.admin_denied"))
            return
        raw = (command.args or "").strip()
        if raw == "":
            await message.answer(catalog.text("bot.refund_page"))
            return
        charge, _, reason = raw.partition(" ")
        if reason.strip() == "":
            await message.answer(catalog.text("bot.refund_need_reason"))
            return
        pending_refund[user.id] = (charge, reason.strip())
        button = InlineKeyboardButton(
            text=catalog.text("bot.refund_confirm"),
            callback_data="refund_confirm",
        )
        await message.answer(
            catalog.text("bot.refund_ask"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
        )

    @router.callback_query(F.data == "refund_confirm")
    async def on_refund_confirmed(query: CallbackQuery) -> None:
        user = query.from_user
        if user.id not in admins:
            await query.answer(catalog.text("bot.admin_denied"), show_alert=False)
            return
        pending = pending_refund.pop(user.id, None)
        await query.answer()
        if pending is None or query.message is None:
            return
        charge, reason = pending
        try:
            await billing.refund(
                actor_is_admin=True,
                charge_id=charge,
                confirm=True,
                reason=reason,
            )
        except FieldInvalid:
            await query.message.answer(catalog.text("errors.not_found"))
            return
        await query.message.answer(catalog.text("bot.refund_done"))

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


async def _stats(
    message: Message,
    catalog: Catalog,
    ops: OpsService,
    admins: frozenset[int],
    cache: bool,
) -> None:
    user = message.from_user
    if user is None or user.id not in admins:
        await message.answer(catalog.text("bot.admin_denied"))
        return
    today = now_utc().date()
    start = datetime.combine(today - timedelta(days=30), time.min, tzinfo=UTC)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=UTC)
    snap = await ops.snapshot(start, end)
    if cache:
        await message.answer(
            catalog.format(
                "bot.cache_stats",
                rows=snap.cache_rows,
                hits=snap.cache_hits,
            )
        )
        return
    errors = sum(item.errors for item in snap.models)
    await message.answer(
        catalog.format(
            "bot.stats",
            users=snap.active_users,
            payments=snap.payments,
            errors=errors,
        )
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
