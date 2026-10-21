"""Сегменты, защита текста и повторы клиента без сети модели."""

import json
from datetime import UTC, datetime, timedelta

import httpx2 as httpx
import pytest
from openai import APIStatusError

from starflow.ai.client import CircuitOpen, DeepSeekClient
from starflow.ai.guard import guarded_copy, plain_text, telegram_chunks
from starflow.cache.ttl import CachedValue, TtlCache
from starflow.domain.segments import (
    cacheable,
    calendar_segment,
    expires_at,
    facts_text,
    forecast_cache_key,
    natal_segment,
    pair_segment,
    period_key,
    personal_segment,
    representative_facts,
    sun_segment,
    synastry_segment,
)
from tests.support import make_settings

MOMENT = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
ZONE = "Europe/Moscow"


def test_same_sun_sign_shares_a_segment_and_chat_is_not_cached() -> None:
    assert sun_segment("козерог") == sun_segment("козерог")
    assert pair_segment("лев", "овен") == pair_segment("овен", "лев")
    assert forecast_cache_key("day", "2026-10-21", "козерог", "", "ru", 1).endswith("|1")
    assert forecast_cache_key("day", "2026-10-21", "козерог", "", "ru", 1) != forecast_cache_key(
        "day",
        "2026-10-21",
        "козерог",
        "",
        "ru",
        2,
    )
    assert cacheable("assistant") is False
    assert cacheable("day") is True
    facts = representative_facts("day", "козерог")
    rendered = facts_text(facts)
    assert facts == {"sun": "козерог"}
    assert "1990" not in rendered
    assert "display_name" not in rendered
    assert personal_segment("козерог", None, None) == "козерог+unknown+unknown"
    assert natal_segment(["козерог"], ["1"], ["соединение"]) == natal_segment(
        ["козерог"],
        ["1"],
        ["соединение"],
    )
    left = {"sun": "овен", "moon": "рак", "asc": None}
    right = {"sun": "лев", "moon": "дева", "asc": "весы"}
    assert synastry_segment(left, right) == synastry_segment(right, left)
    assert calendar_segment("козерог", "рак", None, "2026-10") == "козерог+рак+unknown+2026-10"


def test_shared_periods_expire_on_the_documented_boundary() -> None:
    assert period_key("day", MOMENT, ZONE) == "2026-10-21"
    assert period_key("week", MOMENT, ZONE) == "2026-W43"
    assert period_key("compatibility", MOMENT, ZONE) == "2026-W43"
    assert expires_at("day", MOMENT, ZONE) == datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
    assert expires_at("week", MOMENT, ZONE) == datetime(2026, 10, 25, 21, 0, tzinfo=UTC)
    assert expires_at("calendar", MOMENT, ZONE) == datetime(2026, 10, 31, 21, 0, tzinfo=UTC)
    assert expires_at("natal", MOMENT, ZONE) == datetime(9999, 1, 1, tzinfo=UTC)


def test_memory_entry_does_not_outlive_its_expiry() -> None:
    cache = TtlCache(2)
    moment = datetime(2026, 10, 21, 12, tzinfo=UTC)
    cache.put("a", CachedValue({"title": "один"}, moment + timedelta(minutes=1)))
    cache.put("b", CachedValue({"title": "два"}, moment + timedelta(minutes=1)))
    cache.put("c", CachedValue({"title": "три"}, moment + timedelta(minutes=1)))
    assert cache.get("a", moment) is None
    assert cache.get("b", moment + timedelta(minutes=2)) is None


def test_output_guard_strips_markup_and_telegram_chunks_keep_entities() -> None:
    assert plain_text("Hello **bold** <b>x</b>") == "hello bold x"
    assert guarded_copy("Title", "Спокойный фон") == ("title", "спокойный фон")
    assert guarded_copy("a", "фон 😀") is None
    raw = "x" * 4090 + "& <tag>"
    chunks = telegram_chunks(raw)
    assert chunks
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert "<" not in "".join(chunks)
    assert "&amp;" in "".join(chunks)
    for chunk in chunks:
        assert not chunk.endswith("&")
        assert not chunk.endswith("&a")
        assert not chunk.endswith("&am")


@pytest.mark.asyncio
async def test_client_retries_a_server_error_once() -> None:
    calls = 0
    slept: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, json={"error": {"message": "busy"}})
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
                        "message": {
                            "role": "assistant",
                            "content": '{"title":"сегодня","body":"фон"}',
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    async def sleep(delay: float) -> None:
        slept.append(delay)

    client = DeepSeekClient(
        make_settings(deepseek_max_retries=1),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=sleep,
    )
    reply = await client.complete_forecast(
        model="deepseek-flash",
        system="system",
        user="user",
        temperature=0.2,
        max_tokens=32,
        json_mode=True,
    )
    await client.aclose()
    assert calls == 2
    assert slept
    assert reply.content.startswith("{")


@pytest.mark.asyncio
async def test_circuit_opens_after_five_failed_series() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "down"}})

    client = DeepSeekClient(
        make_settings(deepseek_max_retries=0),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=_asleep,
    )
    for _ in range(5):
        with pytest.raises(APIStatusError):
            await client.complete_forecast(
                model="deepseek-flash",
                system="system",
                user="user",
                temperature=0.2,
                max_tokens=32,
                json_mode=False,
            )
    with pytest.raises(CircuitOpen):
        await client.complete_forecast(
            model="deepseek-flash",
            system="system",
            user="user",
            temperature=0.2,
            max_tokens=32,
            json_mode=False,
        )
    await client.aclose()
    assert calls == 5


async def _asleep(_delay: float) -> None:
    return None


def test_guard_json_is_not_imported_as_html() -> None:
    cleaned = plain_text('{"title":"сегодня","body":"<script>alert(1)</script>"}')
    assert "<" not in cleaned
    assert json.loads('{"ok": true}')["ok"] is True
