"""Вопрос астропомощнику уносит дату и время рождения спрашивающего."""

from datetime import date, time
from pathlib import Path
from uuid import UUID

from starflow.ai.client import ModelReply
from starflow.domain.quota import PremiumRequired
from starflow.domain.stars import SpendResult
from starflow.services.assistant import AssistantService

USER = UUID(int=1)
PROMPT = Path(__file__).resolve().parents[2] / "resources" / "prompts" / "assistant_system.txt"


class _Profile:
    def __init__(self, *, born: date | None, clock: time | None, unknown: bool) -> None:
        self.birth_date = born
        self.birth_time = clock
        self.birth_time_unknown = unknown
        self.timezone = "Europe/Moscow"
        self.display_name = "Анна"


class _Profiles:
    def __init__(self, profile: _Profile) -> None:
        self._profile = profile

    async def ensure(self, _user_id: UUID) -> _Profile:
        return self._profile


class _Messages:
    async def recent(self, _user_id: UUID, _limit: int, _before: object) -> tuple[()]:
        return ()

    async def add(self, *_args: object) -> UUID:
        return UUID(int=2)


class _Requests:
    async def add(self, *_args: object) -> None:
        return None


class _Store:
    def __init__(self, profile: _Profile) -> None:
        self.profiles = _Profiles(profile)
        self.assistant_messages = _Messages()
        self.ai_requests = _Requests()

    async def commit(self) -> None:
        return None


class _Work:
    def __init__(self, profile: _Profile) -> None:
        self._profile = profile

    async def __aenter__(self) -> _Store:
        return _Store(self._profile)

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Quota:
    async def hold(self, *_args: object) -> PremiumRequired:
        return PremiumRequired()

    async def remaining(self, *_args: object) -> None:
        return None


class _Catalog:
    def text(self, key: str) -> str:
        return key


class _Stars:
    async def can_pay(self, *_args: object) -> bool:
        return True

    async def buy(self, *_args: object) -> SpendResult:
        return SpendResult(allowed=True, charged=True, balance=20, price=20)

    async def credit(self, *_args: object) -> int:
        return 40


class _Model:
    def __init__(self) -> None:
        self.facts = ""

    async def complete_messages(self, **kwargs: object) -> ModelReply:
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        facts = messages[1]
        assert isinstance(facts, dict)
        content = facts["content"]
        assert isinstance(content, str)
        self.facts = content
        return ModelReply(
            content='{"reply": "Лев смотрит на этот вечер."}',
            model="deepseek-flash",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
        )


def _service(profile: _Profile, model: _Model) -> AssistantService:
    return AssistantService(
        lambda: _Work(profile),
        model,
        _Quota(),
        _Catalog(),
        system="system",
        model_name="deepseek-flash",
        stars=_Stars(),
    )


def test_assistant_prompt_asks_to_use_the_birth_clock() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    assert "дата и время рождения" in text
    assert "не выдумывай час" in text


async def test_question_sends_the_asker_birth_date_and_time() -> None:
    model = _Model()
    profile = _Profile(born=date(1995, 8, 12), clock=time(14, 30), unknown=False)
    reply = await _service(profile, model).ask(USER, "question-1", "Что с луной сегодня?")
    assert reply.status == "ready"
    assert '"birth_date": "12.08.1995"' in model.facts
    assert '"birth_time": "14:30"' in model.facts
    assert '"timezone": "Europe/Moscow"' in model.facts


async def test_unknown_birth_time_is_not_replaced_with_a_clock() -> None:
    model = _Model()
    profile = _Profile(born=date(1995, 8, 12), clock=None, unknown=True)
    reply = await _service(profile, model).ask(USER, "question-2", "Что с луной сегодня?")
    assert reply.status == "ready"
    assert '"birth_date": "12.08.1995"' in model.facts
    assert '"birth_time": "unknown"' in model.facts
    assert "14:30" not in model.facts
