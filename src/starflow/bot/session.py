"""Telegram session that fails closed.

APP_ENV=test uses it so healthchecks can run without calling Telegram.
A request through this session raises and never returns a successful result.
The Any annotations match aiogram's BaseSession overrides.
"""

from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetMe
from aiogram.methods.base import TelegramMethod

T = TypeVar("T")


class InactiveTelegramSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[T],
        timeout: int | None = None,  # noqa: ASYNC109
    ) -> T:
        del bot, timeout
        raise TelegramNetworkError(
            method=method,
            message="telegram is not contacted when APP_ENV=test",
        )

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,  # noqa: ASYNC109
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        del url, headers, timeout, chunk_size, raise_for_status
        raise TelegramNetworkError(
            method=GetMe(),
            message="telegram file download is not contacted when APP_ENV=test",
        )
        yield b""  # marks this override as an async generator, matching BaseSession
