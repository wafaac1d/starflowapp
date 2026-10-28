"""Вопрос без Premium списывает звёзды до ответа модели."""

from uuid import UUID

from starflow.ai.client import ModelReply
from starflow.domain.quota import PremiumRequired
from starflow.domain.stars import SpendResult
from starflow.services.assistant import AssistantService

USER = UUID(int=1)


class _Profile:
    birth_date = None
    birth_time = None
    display_name = "Анна"


class _Profiles:
    async def ensure(self, _user_id: UUID) -> _Profile:
        return _Profile()


class _Messages:
    async def recent(self, _user_id: UUID, _limit: int, _before: object) -> tuple[()]:
        return ()

    async def add(self, *_args: object) -> UUID:
        return UUID(int=2)


class _Requests:
    async def add(self, *_args: object) -> None:
        return None


class _Store:
    profiles = _Profiles()
    assistant_messages = _Messages()
    ai_requests = _Requests()

    async def commit(self) -> None:
        return None


class _Work:
    async def __aenter__(self) -> _Store:
        return _Store()

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
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def can_pay(self, *_args: object) -> bool:
        return True

    async def buy(self, *_args: object) -> SpendResult:
        self.events.append("buy")
        return SpendResult(allowed=True, charged=True, balance=20, price=20)

    async def credit(self, *_args: object) -> int:
        self.events.append("credit")
        return 40


class _Model:
    def __init__(self, events: list[str], content: str) -> None:
        self.events = events
        self.content = content

    async def complete_messages(self, **_kwargs: object) -> ModelReply:
        self.events.append("model")
        return ModelReply(
            content=self.content,
            model="deepseek-flash",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
        )


def _service(events: list[str], content: str) -> AssistantService:
    return AssistantService(
        lambda: _Work(),
        _Model(events, content),
        _Quota(),
        _Catalog(),
        system="system",
        model_name="deepseek-flash",
        stars=_Stars(events),
    )


async def test_star_question_is_charged_before_the_model() -> None:
    events: list[str] = []
    service = _service(events, '{"reply": "Тихий вечер."}')
    reply = await service.ask(USER, "question-1", "Что с луной сегодня?")
    assert reply.status == "ready"
    assert events == ["buy", "model"]


async def test_failed_star_answer_returns_the_charge() -> None:
    events: list[str] = []
    service = _service(events, "не json")
    reply = await service.ask(USER, "question-2", "Что с луной сегодня?")
    assert reply.status == "error"
    assert events == ["buy", "model", "model", "credit"]
