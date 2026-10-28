"""Рассылка из админки. В очередь попадает пачка, не вся аудитория сразу."""

from dataclasses import dataclass
from uuid import UUID

AUDIENCES = ("all", "inactive", "topup", "premium")
INACTIVE_DAYS = 14
TOPUP_DAYS = 7
BROADCAST_BATCH = 25
BROADCAST_TEXT_MAX = 500


@dataclass(frozen=True)
class BroadcastJob:
    id: UUID
    body: str
    audience: str


def audience_ok(value: str) -> bool:
    return value in AUDIENCES


def broadcast_text_ok(value: str) -> bool:
    cleaned = value.strip()
    return 1 <= len(cleaned) <= BROADCAST_TEXT_MAX
