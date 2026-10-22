"""Ограничение исходящих сообщений бота. Около 25 в секунду."""

import asyncio


class SendPace:
    def __init__(self, per_second: float = 25) -> None:
        if per_second <= 0:
            raise ValueError("pace must be positive")
        self._gap = 1 / per_second
        self._lock = asyncio.Lock()
        self._ready = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            delay = self._ready - now
            if delay > 0:
                await asyncio.sleep(delay)
                now = loop.time()
            self._ready = now + self._gap
