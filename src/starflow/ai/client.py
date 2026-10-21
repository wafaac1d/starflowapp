import httpx2
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from starflow.ai.prompts import PromptLibrary
from starflow.config import Settings


class DeepSeekClient:
    """Клиент DeepSeek через официальный OpenAI SDK. Сеть вызывается только из complete."""

    def __init__(self, settings: Settings, http_client: httpx2.AsyncClient | None = None) -> None:
        self._prompts = PromptLibrary(settings.resources_dir / "prompts")
        self._http = http_client or httpx2.AsyncClient()
        self._sdk = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout_sec,
            max_retries=settings.deepseek_max_retries,
            http_client=self._http,
        )

    async def aclose(self) -> None:
        await self._sdk.close()

    async def complete(self, *, model: str, user_text: str, json_mode: bool) -> str:
        system = self._prompts.assistant_system()
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]
        if json_mode:
            response = await self._sdk.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
        else:
            response = await self._sdk.chat.completions.create(model=model, messages=messages)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("model returned an empty message")
        return content
