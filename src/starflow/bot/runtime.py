import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    WebAppInfo,
)

from starflow.bot.screens import screen_url
from starflow.config import Settings
from starflow.domain.errors import DeliveryBlocked, DeliveryRetry
from starflow.i18n.catalog import Catalog


class BotRuntime:
    def __init__(
        self,
        settings: Settings,
        bot: Bot,
        dispatcher: Dispatcher,
        commands: tuple[BotCommand, ...],
        menu_text: str,
        catalog: Catalog,
    ) -> None:
        self._settings = settings
        self._bot = bot
        self._dispatcher = dispatcher
        self._commands = commands
        self._menu_text = menu_text
        self._catalog = catalog
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._log = structlog.get_logger("bot")

    async def send_text(self, telegram_id: int, text: str) -> None:
        await self.send_notice(telegram_id, text, "")

    async def send_notice(self, telegram_id: int, text: str, page: str) -> None:
        markup = None
        if page and self._settings.mini_app_url:
            url = screen_url(self._settings.mini_app_url, page)
            button = InlineKeyboardButton(
                text=self._catalog.text("bot.open"),
                web_app=WebAppInfo(url=url),
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
        try:
            await self._bot.send_message(telegram_id, text, reply_markup=markup)
        except TelegramRetryAfter as error:
            raise DeliveryRetry(float(error.retry_after)) from error
        except TelegramForbiddenError as error:
            raise DeliveryBlocked() from error

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("bot runtime is already started")
        self._stopped.clear()
        self._task = asyncio.create_task(self._supervise(), name="starflow-bot")

    async def shutdown(self) -> None:
        self._stopped.set()
        if self._settings.bot_mode == "polling":
            try:
                await asyncio.wait_for(self._dispatcher.stop_polling(), timeout=1)
            except (RuntimeError, TimeoutError):
                self._log.info("polling_stop_skipped")
        task = self._task
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._task = None
        await self._bot.session.close()

    async def _configure(self) -> None:
        await self._bot.set_my_commands(list(self._commands))
        if not self._settings.mini_app_url:
            return
        await self._bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=self._menu_text,
                web_app=WebAppInfo(url=self._settings.mini_app_url),
            )
        )

    async def _supervise(self) -> None:
        while not self._stopped.is_set():
            try:
                await self._configure()
                if self._settings.bot_mode == "polling":
                    try:
                        await self._bot.delete_webhook(drop_pending_updates=False)
                    except Exception:
                        pass
                    await self._dispatcher.start_polling(
                        self._bot,
                        handle_signals=False,
                        close_bot_session=False,
                    )
                else:
                    await self._bot.set_webhook(
                        url=self._settings.webhook_url.strip(),
                        secret_token=self._settings.webhook_secret,
                    )
                    self._log.info("webhook_registered")
                    await self._stopped.wait()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._log.warning("bot_supervisor_retry", error_type=type(error).__name__)
                try:
                    await asyncio.wait_for(
                        self._stopped.wait(),
                        timeout=self._settings.bot_retry_sec,
                    )
                except TimeoutError:
                    continue
                return
