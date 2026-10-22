"""Streak растёт по местной дате открытия прогноза и сбрасывается после пропуска."""

from datetime import date, timedelta


def next_streak(last: date | None, today: date, count: int) -> int:
    if last == today:
        return count
    if last is not None and last == today - timedelta(days=1):
        return count + 1
    return 1
