"""Промпты прогноза из YAML. Регистр и emoji проверяются при загрузке."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from starflow.i18n.guard import assert_authored


@dataclass(frozen=True)
class PromptSpec:
    name: str
    version: int
    tier: str
    temperature: float
    max_tokens: int
    output: str
    system: str
    user: str


class PromptCatalog:
    def __init__(self, prompts: dict[str, PromptSpec]) -> None:
        self._prompts = prompts

    def get(self, name: str) -> PromptSpec:
        found = self._prompts.get(name)
        if found is None:
            raise KeyError(name)
        return found


def load_prompts(path: Path) -> PromptCatalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("forecast prompts must be a mapping")
    prompts: dict[str, PromptSpec] = {}
    for name, body in raw.items():
        if not isinstance(name, str) or not isinstance(body, dict):
            raise ValueError("forecast prompt entry is invalid")
        prompts[name] = _spec(name, body)
    return PromptCatalog(prompts)


def _spec(name: str, body: dict[object, object]) -> PromptSpec:
    system = _text(body, "system")
    user = _text(body, "user")
    assert_authored(system)
    assert_authored(user)
    output = _text(body, "output")
    if output != "json_object":
        raise ValueError("forecast output must be json_object")
    tier = _text(body, "tier")
    if tier not in {"fast", "pro"}:
        raise ValueError("forecast tier must be fast or pro")
    version = body.get("version")
    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")
    if not isinstance(version, int) or version < 1:
        raise ValueError("forecast prompt version must be positive")
    if not isinstance(temperature, int | float) or not 0 <= float(temperature) <= 2:
        raise ValueError("forecast temperature is out of range")
    if not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError("forecast max_tokens must be positive")
    return PromptSpec(name, version, tier, float(temperature), max_tokens, output, system, user)


def _text(body: dict[object, object], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"forecast prompt {key} is missing")
    return value.strip()
