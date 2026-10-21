"""Доступ из независимых источников. Grace есть только у рекуррентной подписки."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

SOURCES = ("subscription", "gift", "trial", "referral", "admin")


@dataclass(frozen=True)
class Grant:
    id: UUID
    user_id: UUID
    source: str
    status: str
    period_start: datetime
    period_end: datetime
    grace_until: datetime | None
    revoked_at: datetime | None


def effective_end(grant: Grant) -> datetime:
    if (
        grant.source == "subscription"
        and grant.grace_until is not None
        and grant.grace_until > grant.period_end
    ):
        return grant.grace_until
    return grant.period_end


def grant_is_open(grant: Grant, now: datetime) -> bool:
    if grant.revoked_at is not None or grant.status != "active":
        return False
    if grant.source not in SOURCES:
        return False
    return grant.period_start <= now < effective_end(grant)


def access_end(grants: tuple[Grant, ...], now: datetime) -> datetime | None:
    open_grants = [grant for grant in grants if grant_is_open(grant, now)]
    if not open_grants:
        return None
    return max(effective_end(grant) for grant in open_grants)


def question_grant(grants: tuple[Grant, ...], now: datetime) -> Grant | None:
    """Окно вопросов — период источника, не grace и не календарный месяц."""
    open_grants = [grant for grant in grants if grant_is_open(grant, now)]
    if not open_grants:
        return None
    return max(open_grants, key=effective_end)
