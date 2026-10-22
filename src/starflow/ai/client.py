"""Клиент DeepSeek. Повторы и предохранитель живут здесь, не в SDK."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx2
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from starflow.ai.prompts import PromptLibrary
from starflow.config import Settings


class CircuitOpen(RuntimeError):
    """Предохранитель открыт: сеть в этот вызов не идёт."""


@dataclass(frozen=True)
class ModelReply:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


class CircuitBreaker:
    def __init__(
        self,
        limit: int = 5,
        cooldown_sec: float = 30,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._limit = limit
        self._cooldown = cooldown_sec
        self._clock = clock or time.monotonic
        self._failures = 0
        self._open_until = 0.0

    def allow(self) -> bool:
        return self._clock() >= self._open_until

    def success(self) -> None:
        self._failures = 0
        self._open_until = 0.0

    def failure(self) -> None:
        self._failures += 1
        if self._failures >= self._limit:
            self._open_until = self._clock() + self._cooldown
            self._failures = 0


_THINKING_OFF = {"thinking": {"type": "disabled"}}


class DeepSeekClient:
    """Официальный SDK с выключенными его повторами. JSON-режим — json_object, не схема."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx2.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._prompts = PromptLibrary(settings.resources_dir / "prompts")
        self._attempts = settings.deepseek_max_retries + 1
        self._sleep = sleep or asyncio.sleep
        self._breaker = breaker or CircuitBreaker()
        self._http = http_client or httpx2.AsyncClient()
        self._sdk = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout_sec,
            max_retries=0,
            http_client=self._http,
        )

    async def aclose(self) -> None:
        await self._sdk.close()

    async def complete(self, *, model: str, user_text: str, json_mode: bool) -> str:
        system = self._prompts.assistant_system()
        reply = await self.complete_forecast(
            model=model,
            system=system,
            user=user_text,
            temperature=0.2,
            max_tokens=512,
            json_mode=json_mode,
        )
        return reply.content

    async def complete_forecast(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelReply:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        started = time.monotonic()

        async def call() -> ChatCompletion:
            return await self._create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )

        response = await self._run(call)
        return self._reply(response, started)

    async def complete_messages(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelReply:
        """В вызов не передаются tools: текст пользователя не запускает код и чужие чтения."""
        payload: list[ChatCompletionMessageParam] = []
        for item in messages:
            role = item.get("role")
            content = item.get("content", "")
            if role == "system":
                payload.append({"role": "system", "content": content})
            elif role == "user":
                payload.append({"role": "user", "content": content})
            elif role == "assistant":
                payload.append({"role": "assistant", "content": content})
        started = time.monotonic()

        async def call() -> ChatCompletion:
            return await self._create(
                model=model,
                messages=payload,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )

        response = await self._run(call)
        return self._reply(response, started)

    async def _create(
        self,
        *,
        model: str,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ChatCompletion:
        if json_mode:
            return await self._sdk.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort="none",
                response_format={"type": "json_object"},
                extra_body=_THINKING_OFF,
            )
        return await self._sdk.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort="none",
            extra_body=_THINKING_OFF,
        )

    def _reply(self, response: ChatCompletion, started: float) -> ModelReply:
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("model returned an empty message")
        usage = response.usage
        return ModelReply(
            content=content,
            model=response.model,
            prompt_tokens=None if usage is None else usage.prompt_tokens,
            completion_tokens=None if usage is None else usage.completion_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def _run(self, call: Callable[[], Awaitable[ChatCompletion]]) -> ChatCompletion:
        if not self._breaker.allow():
            raise CircuitOpen("circuit is open")
        delay = 0.2
        last: BaseException | None = None
        for attempt in range(self._attempts):
            try:
                response = await call()
            except Exception as exc:
                last = exc
                if not _retryable(exc) or attempt + 1 == self._attempts:
                    self._breaker.failure()
                    raise
                await self._sleep(delay + random.uniform(0, delay))
                delay *= 2
                continue
            self._breaker.success()
            return response
        if last is not None:
            raise last
        raise RuntimeError("model call did not run")


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, APITimeoutError | APIConnectionError | TimeoutError):
        return True
    return isinstance(exc, APIStatusError) and (exc.status_code == 429 or exc.status_code >= 500)
