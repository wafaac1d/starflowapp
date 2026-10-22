"""Сроки хранения. Платёжный след сюда не входит."""

from datetime import datetime, timedelta

CACHE_DAYS = 14
HISTORY_DAYS = 400
AI_DAYS = 90
OUTBOX_DAYS = 30
IDEMPOTENCY_DAYS = 14
ASSISTANT_DAYS = 400
GEOCODE_DAYS = 180


def cutoff(moment: datetime, days: int) -> datetime:
    return moment - timedelta(days=days)
