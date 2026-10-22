import json
from pathlib import Path

import httpx2 as httpx
import pytest

from starflow.ai.client import DeepSeekClient
from starflow.api.app import build_fastapi
from starflow.bootstrap import build_container
from tests.support import make_settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_deepseek_client_posts_the_configured_model() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "id": "1",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"reply":"строчный ответ"}'},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    settings = make_settings()
    client = DeepSeekClient(
        settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    text = await client.complete(
        model=settings.deepseek_model_fast,
        user_text="верни json",
        json_mode=True,
    )
    assert text == '{"reply":"строчный ответ"}'
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-flash"
    assert body["response_format"] == {"type": "json_object"}
    assert "tools" not in body
    assert "api.deepseek.com" in str(seen["url"])
    seen.clear()
    await client.complete_messages(
        model=settings.deepseek_model_fast,
        messages=[
            {"role": "system", "content": "системный текст"},
            {"role": "user", "content": "Что с Луной?"},
        ],
        temperature=0.2,
        max_tokens=400,
        json_mode=True,
    )
    chat = seen["body"]
    assert isinstance(chat, dict)
    assert "tools" not in chat
    assert chat["messages"][0]["content"] == "системный текст"
    assert chat["messages"][1] == {"role": "user", "content": "Что с Луной?"}
    await client.aclose()


def test_openapi_document_matches_the_committed_contract() -> None:
    app = build_fastapi(build_container(make_settings()))
    schema = app.openapi()
    committed = json.loads((ROOT / "frontend" / "openapi.json").read_text(encoding="utf-8"))
    assert schema == committed
