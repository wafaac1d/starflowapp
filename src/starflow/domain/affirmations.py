"""Домен аффирмаций на день."""

from dataclasses import dataclass

from starflow.domain.errors import FieldInvalid

CATEGORIES: dict[str, str] = {
    "for_you": "Для вас",
    "confidence": "Уверенность",
    "calm": "Спокойствие",
}


@dataclass(frozen=True)
class AffirmationCard:
    id: str
    text: str
    category: str
    bg_image: str


DEFAULT_AFFIRMATIONS: dict[str, tuple[AffirmationCard, ...]] = {
    "for_you": (
        AffirmationCard(
            id="for_you_1",
            category="for_you",
            text="«Я доверяю себе\nи выбираю свой ритм.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_01.png",
        ),
        AffirmationCard(
            id="for_you_2",
            category="for_you",
            text="«Каждый мой шаг приближает\nменя к гармонии и ясности.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_02.png",
        ),
        AffirmationCard(
            id="for_you_3",
            category="for_you",
            text="«Я открываюсь новому дню\nс лёгкостью и благодарностью.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_03.png",
        ),
    ),
    "confidence": (
        AffirmationCard(
            id="confidence_1",
            category="confidence",
            text="«Во мне есть всё необходимое,\nчтобы справиться с любыми задачами.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_01.png",
        ),
        AffirmationCard(
            id="confidence_2",
            category="confidence",
            text="«Моя внутренняя сила растёт\nс каждым осознанным решением.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_02.png",
        ),
        AffirmationCard(
            id="confidence_3",
            category="confidence",
            text="«Я верю в свои возможности\nи смело иду вперёд.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_03.png",
        ),
    ),
    "calm": (
        AffirmationCard(
            id="calm_1",
            category="calm",
            text="«Я отпускаю спешку\nи нахожу покой в настоящем моменте.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_01.png",
        ),
        AffirmationCard(
            id="calm_2",
            category="calm",
            text="«Тишина внутри меня\nсильнее любой внешней суеты.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_02.png",
        ),
        AffirmationCard(
            id="calm_3",
            category="calm",
            text="«Моё дыхание ровное,\nа мысли ясные и безмятежные.»",
            bg_image="/affirmations/affirmation_backgrounds/affirmation_background_03.png",
        ),
    ),
}


def category_label(category: str) -> str:
    cleaned = category.strip().casefold()
    found = CATEGORIES.get(cleaned)
    if found is None:
        raise FieldInvalid("category", "errors.validation")
    return found
