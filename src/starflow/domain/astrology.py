"""Знак, стихия, модальность, декан и мажорный аспект.

Дома Плацидуса, орбисы и лунный день описаны в D-033. Этот модуль не обращается
к эфемеридам: он раскладывает уже известную долготу.
"""

import math
from dataclasses import dataclass

from starflow.astro.ecliptic import SIGNS, sign_for_longitude

ELEMENTS = ("огонь", "земля", "воздух", "вода")
MODALITIES = ("кардинальный", "фиксированный", "мутабельный")

_ELEMENT_BY_SIGN = {
    "овен": "огонь",
    "телец": "земля",
    "близнецы": "воздух",
    "рак": "вода",
    "лев": "огонь",
    "дева": "земля",
    "весы": "воздух",
    "скорпион": "вода",
    "стрелец": "огонь",
    "козерог": "земля",
    "водолей": "воздух",
    "рыбы": "вода",
}
_MODALITY_BY_SIGN = {
    "овен": "кардинальный",
    "телец": "фиксированный",
    "близнецы": "мутабельный",
    "рак": "кардинальный",
    "лев": "фиксированный",
    "дева": "мутабельный",
    "весы": "кардинальный",
    "скорпион": "фиксированный",
    "стрелец": "мутабельный",
    "козерог": "кардинальный",
    "водолей": "фиксированный",
    "рыбы": "мутабельный",
}
_RULER_BY_SIGN = {
    "овен": "марс",
    "телец": "венера",
    "близнецы": "меркурий",
    "рак": "луна",
    "лев": "солнце",
    "дева": "меркурий",
    "весы": "венера",
    "скорпион": "марс",
    "стрелец": "юпитер",
    "козерог": "сатурн",
    "водолей": "сатурн",
    "рыбы": "юпитер",
}
# Халдейские управители деканов. Овен начинается с Марса, дальше по 10°.
_DECAN_RULERS = (
    "марс",
    "солнце",
    "венера",
    "меркурий",
    "луна",
    "сатурн",
    "юпитер",
    "марс",
    "солнце",
    "венера",
    "меркурий",
    "луна",
    "сатурн",
    "юпитер",
    "марс",
    "солнце",
    "венера",
    "меркурий",
    "луна",
    "сатурн",
    "юпитер",
    "марс",
    "солнце",
    "венера",
    "меркурий",
    "луна",
    "сатурн",
    "юпитер",
    "марс",
    "солнце",
    "венера",
    "меркурий",
    "луна",
    "сатурн",
    "юпитер",
    "марс",
)

# Угол и орб. Соединение — 0°.
ASPECTS = (
    (0.0, 8.0, "соединение"),
    (60.0, 4.0, "секстиль"),
    (90.0, 6.0, "квадрат"),
    (120.0, 6.0, "трин"),
    (180.0, 8.0, "оппозиция"),
)
DECAN_WIDTH = 10.0
MOON_DAY_MOTION = 13.0


@dataclass(frozen=True)
class SignFacts:
    sign: str
    element: str
    modality: str
    ruler: str
    decan: int
    decan_ruler: str
    degree_in_sign: float


@dataclass(frozen=True)
class AspectHit:
    first: str
    second: str
    name: str
    orb: float


def facts_for_longitude(longitude: float) -> SignFacts:
    sign = sign_for_longitude(longitude)
    degree = longitude % 30
    decan = min(3, int(degree // DECAN_WIDTH) + 1)
    index = SIGNS.index(sign) * 3 + (decan - 1)
    return SignFacts(
        sign=sign,
        element=_ELEMENT_BY_SIGN[sign],
        modality=_MODALITY_BY_SIGN[sign],
        ruler=_RULER_BY_SIGN[sign],
        decan=decan,
        decan_ruler=_DECAN_RULERS[index],
        degree_in_sign=degree,
    )


def moon_near_cusp(longitude: float, window: float = MOON_DAY_MOTION / 2) -> bool:
    degree = longitude % 30
    return degree <= window or degree >= 30 - window


def aspects_between(longitudes: dict[str, float]) -> tuple[AspectHit, ...]:
    names = list(longitudes)
    found: list[AspectHit] = []
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            hit = _aspect(
                names[left],
                longitudes[names[left]],
                names[right],
                longitudes[names[right]],
            )
            if hit is not None:
                found.append(hit)
    return tuple(found)


def transit_aspects(
    natal: dict[str, float],
    sky: dict[str, float],
) -> tuple[AspectHit, ...]:
    found: list[AspectHit] = []
    for natal_name, natal_longitude in natal.items():
        for sky_name, sky_longitude in sky.items():
            hit = _aspect(natal_name, natal_longitude, sky_name, sky_longitude)
            if hit is not None:
                found.append(hit)
    return tuple(found)


def phase_name(sun_longitude: float, moon_longitude: float) -> str:
    elongation = (moon_longitude - sun_longitude) % 360
    if elongation < 22.5 or elongation >= 337.5:
        return "новолуние"
    if elongation < 67.5:
        return "растущий серп"
    if elongation < 112.5:
        return "первая четверть"
    if elongation < 157.5:
        return "растущая луна"
    if elongation < 202.5:
        return "полнолуние"
    if elongation < 247.5:
        return "убывающая луна"
    if elongation < 292.5:
        return "последняя четверть"
    return "убывающий серп"


def _aspect(first: str, left: float, second: str, right: float) -> AspectHit | None:
    if not math.isfinite(left) or not math.isfinite(right):
        raise ValueError("aspect longitude must be finite")
    separation = abs(left - right) % 360
    if separation > 180:
        separation = 360 - separation
    for angle, orb, name in ASPECTS:
        delta = abs(separation - angle)
        if delta <= orb:
            return AspectHit(first, second, name, delta)
    return None
