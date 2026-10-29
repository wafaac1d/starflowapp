"""Домен обращений в поддержку."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from starflow.i18n.guard import contains_emoji


@dataclass(frozen=True)
class SupportTicket:
    id: UUID
    user_id: UUID
    telegram_id: int
    username: str | None
    display_name: str | None
    subject: str
    message: str
    status: str
    created_at: datetime
    closed_at: datetime | None


def support_subject_ok(subject: str) -> bool:
    cleaned = subject.strip()
    if len(cleaned) < 2 or len(cleaned) > 100:
        return False
    return not contains_emoji(cleaned)


def support_message_ok(message: str) -> bool:
    cleaned = message.strip()
    if len(cleaned) < 5 or len(cleaned) > 2000:
        return False
    return not contains_emoji(cleaned)
