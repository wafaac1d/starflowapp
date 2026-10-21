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
    TelegramObject,
    WebAppInfo,
)

from starflow.bot.screens import SCREENS, screen_url
from starflow.i18n.catalog import Catalog
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
) -> None:
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
