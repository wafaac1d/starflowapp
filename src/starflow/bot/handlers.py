import asyncio
import contextlib
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
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
    TelegramObject,
    WebAppInfo,
)

from starflow.bot.screens import SCREENS, screen_url
from starflow.domain.errors import FieldInvalid
from starflow.domain.time import now_utc
from starflow.i18n.catalog import Catalog
from starflow.i18n.guard import redact
from starflow.services.billing import BillingService
from starflow.services.ops import OpsService
from starflow.services.session import SessionService

_LOG = structlog.get_logger("bot")
_bg_tasks: set[asyncio.Task[None]] = set()

WELCOME_MESSAGE = (
    "Добро пожаловать в обсерваторию StarFlow! 🔭\n\n"
    "Открой приложение, чтобы продолжить — нажми на кнопку под сообщением 👇 "
)

FOLLOWUP_MESSAGE = (
    "Я не отвечаю команды, а всё самое интересное — в обсерватории StarFlow 🔭\n\n"
    "Нажми на кнопку ниже, чтобы открыть приложение 👇"
)

BUTTON_TEXT = "Открыть StarFlow"


class UpdateContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        update = data.get("event_update")
        update_id = getattr(update, "update_id", None)
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        telegram_id = getattr(user, "id", None) if user is not None else None

        request_type = "bot.unknown"
        params: dict[str, Any] = {}
        if isinstance(event, Message):
            if event.successful_payment is not None:
                pay = event.successful_payment
                request_type = "bot.successful_payment"
                params = {
                    "currency": pay.currency,
                    "total_amount": pay.total_amount,
                    "invoice_payload": pay.invoice_payload,
                }
            elif event.text and event.text.startswith("/"):
                parts = event.text.split(maxsplit=1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                request_type = f"bot.command_{cmd.lstrip('/')}"
                params = {"command": cmd, "args": args}
            else:
                request_type = "bot.message"
                params = {"text": event.text or ""}
        elif isinstance(event, CallbackQuery):
            request_type = "bot.callback_query"
            params = {"data": event.data or ""}
        elif isinstance(event, PreCheckoutQuery):
            request_type = "bot.pre_checkout_query"
            params = {
                "currency": event.currency,
                "total_amount": event.total_amount,
                "invoice_payload": event.invoice_payload,
            }
        else:
            request_type = f"bot.{type(event).__name__.lower()}"

        bound: dict[str, Any] = {
            "request_type": request_type,
            "params": redact(params),
        }
        if isinstance(update_id, int):
            bound["update_id"] = update_id
        if isinstance(telegram_id, int):
            bound["telegram_id"] = telegram_id
            bound["telegramId"] = telegram_id
            bound["user_id"] = telegram_id
        structlog.contextvars.bind_contextvars(**bound)

        _LOG.info(
            "bot_request",
            telegramId=telegram_id,
            telegram_id=telegram_id,
            request_type=request_type,
            params=redact(params),
        )
        try:
            return await handler(event, data)
        finally:
            structlog.contextvars.unbind_contextvars(
                "update_id", "user_id", "telegram_id", "telegramId", "request_type", "params"
            )


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
        structlog.contextvars.bind_contextvars(
            telegram_id=user.id, telegramId=user.id, user_id=user.id
        )
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
        structlog.contextvars.bind_contextvars(
            telegram_id=user.id, telegramId=user.id, user_id=user.id
        )
        await session_service.accept_telegram_user(
            user.id,
            user.username,
            user.language_code,
            command.args,
        )
        is_first = await session_service.mark_bot_welcomed(user.id)
        if is_first:
            await _reply_welcome(message, catalog, mini_app_url)
        else:
            await _reply_followup(message, catalog, mini_app_url)

    for screen in SCREENS:
        _register_screen(router, session_service, catalog, mini_app_url, screen)

    @router.message(Command("delete_me"))
    async def on_delete(message: Message) -> None:
        user = message.from_user
        if user is not None:
            structlog.contextvars.bind_contextvars(
                telegram_id=user.id, telegramId=user.id, user_id=user.id
            )
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
        structlog.contextvars.bind_contextvars(
            telegram_id=user.id, telegramId=user.id, user_id=user.id
        )
        await session_service.accept_telegram_user(
            user.id,
            user.username,
            user.language_code,
            None,
        )
        is_first = await session_service.mark_bot_welcomed(user.id)
        if is_first:
            await _reply_welcome(message, catalog, mini_app_url)
        else:
            await _reply_followup(message, catalog, mini_app_url)

    @router.callback_query(F.data == "delete_me")
    async def on_delete_confirmed(query: CallbackQuery) -> None:
        user = query.from_user
        structlog.contextvars.bind_contextvars(
            telegram_id=user.id, telegramId=user.id, user_id=user.id
        )
        removed = await session_service.delete_telegram_account(user.id)
        text = catalog.text("bot.delete_done" if removed else "bot.delete_missing")
        await query.answer()
        if query.message is not None:
            await query.message.answer(text)


def _register_screen(
    router: Router,
    session_service: SessionService,
    catalog: Catalog,
    mini_app_url: str,
    screen: str,
) -> None:
    @router.message(Command(screen))
    async def on_screen(message: Message) -> None:
        user = message.from_user
        if user is not None:
            structlog.contextvars.bind_contextvars(
                telegram_id=user.id, telegramId=user.id, user_id=user.id
            )
            is_first = await session_service.mark_bot_welcomed(user.id)
            if is_first:
                await _reply_welcome(message, catalog, mini_app_url)
                return
        await _reply_followup(message, catalog, mini_app_url)


def _make_keyboards(
    mini_app_url: str, button_text: str = "Открыть StarFlow"
) -> tuple[InlineKeyboardMarkup | None, ReplyKeyboardMarkup | None]:
    if not mini_app_url:
        return None, None
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=mini_app_url))]
        ]
    )
    reply_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button_text, web_app=WebAppInfo(url=mini_app_url))]],
        resize_keyboard=True,
    )
    return inline_kb, reply_kb


async def _reply_welcome(
    message: Message,
    catalog: Catalog,
    mini_app_url: str,
) -> None:
    if not mini_app_url:
        await message.answer(catalog.text("bot.start_without_app"))
        return
    text = WELCOME_MESSAGE
    button_text = BUTTON_TEXT
    inline_kb, _ = _make_keyboards(mini_app_url, button_text)
    await message.answer(
        text,
        reply_markup=inline_kb,
    )
    bot = message.bot
    if bot is not None:

        async def _set_menu() -> None:
            with contextlib.suppress(Exception):
                await bot.set_chat_menu_button(
                    chat_id=message.chat.id,
                    menu_button=MenuButtonWebApp(
                        text=button_text,
                        web_app=WebAppInfo(url=mini_app_url),
                    ),
                )

        task = asyncio.create_task(_set_menu())
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)


async def _reply_followup(
    message: Message,
    catalog: Catalog,
    mini_app_url: str,
) -> None:
    if not mini_app_url:
        await message.answer(catalog.text("bot.start_without_app"))
        return
    text = FOLLOWUP_MESSAGE
    button_text = BUTTON_TEXT
    inline_kb, _ = _make_keyboards(mini_app_url, button_text)
    await message.answer(
        text,
        reply_markup=inline_kb,
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
