"""Контекст помощника. Вопрос остаётся сообщением user и не дописывается в system."""

from dataclasses import dataclass
from datetime import datetime

QUESTION_LIMIT = 500
HISTORY_LIMIT = 8
TOKEN_BUDGET = 1500

_ASTRO_STEMS = (
    "гороскоп",
    "знак",
    "лун",
    "солн",
    "асценд",
    "натал",
    "синастр",
    "транзит",
    "ретро",
    "зодиак",
    "планет",
    "меркур",
    "венер",
    "марс",
    "юпитер",
    "сатурн",
    "уран",
    "нептун",
    "плутон",
    "совмест",
    "прогноз",
    "астрол",
    "отношен",
    "работ",
    "финанс",
    "эмоц",
    "карт",
    "дом",
    "недел",
    "месяц",
    "завтра",
    "сегодня",
)
_ROLE = frozenset({"system", "assistant", "системн", "инструкц"})
_OVERRIDE = frozenset({"ignore", "игнорируй", "забудь", "override", "jailbreak"})
_IMPERATIVE = frozenset(
    {"выполни", "execute", "запусти", "run", "покажи", "выведи", "print", "reveal"}
)
_TOOL = frozenset({"код", "code", "tool", "tools", "инструмент", "sql", "команду", "shell"})
_FOREIGN = frozenset({"чужой", "чужие", "чужих", "другого", "других", "user"})
_SECRET = frozenset({"данные", "профил", "профиль", "секрет", "парол", "токен", "prompt", "промпт"})


@dataclass(frozen=True)
class StoredTurn:
    created_at: datetime
    role: str
    content: str


def classify(text: str, *, has_context: bool) -> str:
    """Категории токенов, не одно регулярное выражение. Новая формулировка может пройти."""
    tokens = _tokens(text)
    if _injection(tokens):
        return "injection"
    if any(stem in token for token in tokens for stem in _ASTRO_STEMS):
        return "allow"
    if has_context and 0 < len(tokens) <= 8:
        return "allow"
    return "off_topic"


def pack_messages(
    system: str,
    profile_facts: str,
    history: tuple[tuple[str, str], ...],
    question: str,
) -> list[dict[str, str]]:
    system_message = {"role": "system", "content": system}
    profile_message = {"role": "user", "content": profile_facts}
    question_message = {"role": "user", "content": question}
    selected = [(role, content) for role, content in history if role in {"user", "assistant"}][
        -HISTORY_LIMIT:
    ]
    packed = _assemble(system_message, profile_message, selected, question_message)
    while _estimate(packed) > TOKEN_BUDGET and selected:
        selected = selected[1:]
        packed = _assemble(system_message, profile_message, selected, question_message)
    return packed


def page_turns(
    turns: tuple[StoredTurn, ...],
    *,
    limit: int,
    before: datetime | None,
) -> tuple[StoredTurn, ...]:
    pool = [item for item in turns if before is None or item.created_at < before]
    pool.sort(key=lambda item: item.created_at)
    if len(pool) <= limit:
        return tuple(pool)
    return tuple(pool[-limit:])


def _assemble(
    system_message: dict[str, str],
    profile_message: dict[str, str],
    history: list[tuple[str, str]],
    question_message: dict[str, str],
) -> list[dict[str, str]]:
    body = [system_message, profile_message]
    body.extend({"role": role, "content": content} for role, content in history)
    body.append(question_message)
    return body


def _estimate(messages: list[dict[str, str]]) -> int:
    return sum(len(item["content"]) for item in messages) // 4 + 1


def _tokens(text: str) -> tuple[str, ...]:
    cleaned = "".join(character if character.isalnum() else " " for character in text.casefold())
    return tuple(part for part in cleaned.split() if part)


def _injection(tokens: tuple[str, ...]) -> bool:
    role_hijack = _has(tokens, _ROLE) and _has(tokens, _OVERRIDE)
    tool_call = _has(tokens, _IMPERATIVE) and _has(tokens, _TOOL)
    foreign = _has(tokens, _FOREIGN) and _has(tokens, _SECRET)
    dump_targets = ("промпт", "prompt", "системн", "инструкц")
    prompt_dump = _has(tokens, _IMPERATIVE) and _has(tokens, _SECRET) and _has(tokens, dump_targets)
    return role_hijack or tool_call or foreign or prompt_dump


def _has(tokens: tuple[str, ...], stems: tuple[str, ...] | frozenset[str]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in stems)
