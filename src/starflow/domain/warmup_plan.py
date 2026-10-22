"""Общий прогрев: 12 солнечных знаков в день и 78 пар с повторениями в неделю."""

from itertools import combinations_with_replacement

SIGNS: tuple[str, ...] = (
    "овен",
    "телец",
    "близнецы",
    "рак",
    "лев",
    "дева",
    "весы",
    "скорпион",
    "стрелец",
    "козерог",
    "водолей",
    "рыбы",
)

WARM_BUDGET = 20
WARM_PARALLEL = 3


def unordered_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(combinations_with_replacement(SIGNS, 2))
