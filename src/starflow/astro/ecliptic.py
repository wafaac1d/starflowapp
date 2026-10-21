"""Классификация эклиптической долготы.

Это не эфемериды и не натальная карта: функция не вычисляет положение светила.
"""

import math

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


def sign_for_longitude(longitude: float) -> str:
    if not math.isfinite(longitude):
        raise ValueError("longitude must be finite")
    normalized = longitude % 360
    index = int(normalized // 30) % 12
    return SIGNS[index]
