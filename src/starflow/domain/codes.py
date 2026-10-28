"""Коды на баланс. Их выдаёт только админ, купить код нельзя."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

CODE_NAME_MIN = 3
CODE_NAME_MAX = 32
CODE_USES_MAX = 10000
CODE_DAYS_MAX = 366


@dataclass(frozen=True)
class BalanceCode:
    id: UUID
    code: str
    stars: int
    max_uses: int
    used_count: int
    expires_at: datetime


def code_name_ok(value: str) -> bool:
    cleaned = value.strip()
    if not CODE_NAME_MIN <= len(cleaned) <= CODE_NAME_MAX:
        return False
    return all(character.isalnum() or character in {"_", "-"} for character in cleaned)


def code_uses_ok(value: int) -> bool:
    return 1 <= value <= CODE_USES_MAX


def code_days_ok(value: int) -> bool:
    return 1 <= value <= CODE_DAYS_MAX
