"""Имена функций. Лимиты читаются из правила YAML, не из этих строк."""

FORECAST_TYPES = (
    "day",
    "week",
    "advice",
    "moon",
    "compatibility",
    "personal_day",
    "personal_week",
    "topics",
    "natal",
    "calendar",
    "synastry",
    "retrospective",
)
TOPICS = ("стихия", "модальность", "управитель")
GATES = ("open", "metered", "capacity", "premium")
PERIODS = ("user_week", "paid_period")
FEATURE_CODES = (
    "day",
    "week",
    "advice",
    "moon",
    "compatibility",
    "favorite",
    "related_profile",
    "personal_day",
    "personal_week",
    "topics",
    "natal",
    "calendar",
    "synastry",
    "retrospective",
    "assistant",
)


def cache_key(kind: str, owner: str, fingerprint: str) -> str:
    return f"{kind}:{owner}:{fingerprint}"
