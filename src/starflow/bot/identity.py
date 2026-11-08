"""Имя бота для ссылок, которые должны открываться в Telegram."""

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError

from starflow.domain.invite import clean_bot_username


class BotIdentity:
    def __init__(self, bot: Bot, configured: str) -> None:
        self._bot = bot
        self._username = clean_bot_username(configured)
        self._lock = asyncio.Lock()

    async def username(self) -> str:
        if self._username:
            return self._username
        async with self._lock:
            if self._username:
                return self._username
            try:
                me = await self._bot.get_me()
            except (TelegramAPIError, TelegramNetworkError):
                return ""
            self._username = clean_bot_username(me.username)
            return self._username
