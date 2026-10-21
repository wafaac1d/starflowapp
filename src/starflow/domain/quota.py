"""Итог проверки доступа. Списание живёт в QuotaService, не в этих значениях."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Allowed:
    """Можно выполнять действие. preview ничего не резервирует."""


@dataclass(frozen=True)
class LimitReached:
    reset_at: datetime | None


@dataclass(frozen=True)
class PremiumRequired:
    """Платный контур закрыт. Это не исключение транспорта."""


QuotaDecision = Allowed | LimitReached | PremiumRequired


def idempotency_key_ok(value: str) -> bool:
    if len(value) < 8 or len(value) > 80:
        return False
    return all(character.isalnum() or character in {"_", "-"} for character in value)
