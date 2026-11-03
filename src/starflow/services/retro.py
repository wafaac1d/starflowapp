"""Разбор влияния ретроградной планеты для пользователя."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from types import TracebackType
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from structlog import get_logger

from starflow.ai.catalog import PromptCatalog
from starflow.ai.client import ModelReply
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import FieldInvalid
from starflow.domain.segments import facts_text
from starflow.domain.stars import RETROGRADE_STARS, retrograde_subject
from starflow.domain.time import now_utc
from starflow.repositories.sql import (
    AiRequestRepository,
    ProfileRepository,
    SubscriptionRepository,
)

_LOG = get_logger("retro")
_REPAIR = "Верни только один валидный json-объект без markdown-разметки."

KNOWN_PLANETS = frozenset(
    {"меркурий", "венера", "марс", "юпитер", "сатурн", "уран", "нептун", "плутон"}
)

PLANET_NAMES: dict[str, str] = {
    "меркурий": "Меркурий",
    "венера": "Венера",
    "марс": "Марс",
    "юпитер": "Юпитер",
    "сатурн": "Сатурн",
    "уран": "Уран",
    "нептун": "Нептун",
    "плутон": "Плутон",
}

FALLBACKS: dict[str, dict[str, str]] = {
    "меркурий": {
        "title": "Ретроградный Меркурий: пересмотр и внимание к деталям",
        "body": (
            "Этот период связан с замедлением привычного ритма информации и коммуникаций. "
            "Возможны задержки в поездках, оформлении документов и возвращение к делам прошлого. "
            "Для вас это ценное время, чтобы пересмотреть договорённости, навести порядок в планах "
            "и уделить внимание деталям, которые раньше ускользали от внимания."
        ),
        "advice": (
            "Перепроверяйте важные документы перед отправкой, сохраняйте спокойствие "
            "при переносах встреч и избегайте импульсивных покупок сложной техники."
        ),
    },
    "венера": {
        "title": "Ретроградная Венера: переоценка ценностей и гармония",
        "body": (
            "Ретроградное движение Венеры направляет фокус внутрь — на сферу личных отношений, "
            "эстетики и финансового баланса. В этот период на поверхность могут выходить вопросы "
            "взаимных ожиданий. Это благоприятный момент для переосмысления того, "
            "что действительно приносит вам радость и душевный покой."
        ),
        "advice": (
            "Не торопитесь с кардинальными решениями в личной жизни "
            "и воздержитесь от крупных спонтанных трат на предметы роскоши."
        ),
    },
    "марс": {
        "title": "Ретроградный Марс: распределение сил и перегруппировка",
        "body": (
            "Влияние ретроградного Марса смещает внешнюю активность в русло внутреннего анализа "
            "и переоценки целей. Прямые действия и напор могут встречать временное сопротивление. "
            "Период отлично подходит для завершения давно начатых проектов, "
            "требующих выдержки и стратегического терпения."
        ),
        "advice": (
            "Избегайте ненужной конфронтации, не растрачивайте энергию на импульсивные начинания "
            "и распределяйте физическую нагрузку осознанно."
        ),
    },
    "юпитер": {
        "title": "Ретроградный Юпитер: поиск внутренних ориентиров",
        "body": (
            "Ретроградная фаза Юпитера смещает внимание с внешней экспансии на внутренний рост, "
            "философию и личные идеалы. Для вас это возможность глубже взглянуть на свои "
            "долгосрочные жизненные ориентиры, освободившись от чужих ожиданий."
        ),
        "advice": (
            "Сосредоточьтесь на углублении уже имеющихся знаний и навыков, "
            "не гонясь за быстрыми результатами."
        ),
    },
    "сатурн": {
        "title": "Ретроградный Сатурн: укрепление фундамента и дисциплина",
        "body": (
            "Период Сатурна обращает внимание на структуру, границы и ответственность. "
            "Могут актуализироваться вопросы личных обязательств и долгосрочной устойчивости. "
            "Это время наведения порядка в делах и проверки устойчивости ваших планов."
        ),
        "advice": (
            "Не уклоняйтесь от рутинных обязательств, "
            "шаг за шагом закрывайте накопившиеся организационные вопросы."
        ),
    },
    "уран": {
        "title": "Ретроградный Уран: внутренняя свобода и озарения",
        "body": (
            "Ретроградность Урана активирует процессы внутреннего освобождения от шаблонов. "
            "Неожиданные мысли и озарения могут подсказать нестандартные решения для задач. "
            "Это период личного обновления без разрушения того, что вам дорого."
        ),
        "advice": (
            "Будьте открыты новым идеям и переменам, "
            "но не спешите с необдуманным разрывом устоявшихся связей."
        ),
    },
    "нептун": {
        "title": "Ретроградный Нептун: интуиция и снятие иллюзий",
        "body": (
            "Ретроградный Нептун усиливает тонкую восприимчивость, интуицию и интерес "
            "к внутреннему миру. Период помогает мягко рассеять иллюзии и взглянуть "
            "на реальность без самообмана, находя гармонию в творчестве и покое."
        ),
        "advice": ("Доверяйте интуиции, но проверяйте факты при принятии практических решений."),
    },
    "плутон": {
        "title": "Ретроградный Плутон: глубинная трансформация и сила",
        "body": (
            "Период ретроградного Плутона связан с глубокой внутренней трансформацией "
            "и освобождением от отживших моделей поведения. Это время мощного очищения, "
            "восстановления стойкости и осознания своей истинной силы."
        ),
        "advice": (
            "Отпускайте то, что больше не служит развитию, "
            "и направляйте внимание на внутреннее укрепление."
        ),
    },
}


@dataclass(frozen=True)
class RetroMeaningView:
    planet: str
    start: str
    end: str
    access: str
    price: int
    title: str
    body: str
    advice: str


class RetroStore(Protocol):
    profiles: ProfileRepository
    ai_requests: AiRequestRepository
    subscriptions: SubscriptionRepository

    async def commit(self) -> None: ...


class RetroWork(Protocol):
    async def __aenter__(self) -> RetroStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class RetroStars(Protocol):
    async def owns(self, user_id: UUID, feature: str, subject: str) -> bool: ...


class TextModel(Protocol):
    async def complete_forecast(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelReply: ...


class RetroService:
    def __init__(
        self,
        uow_factory: Callable[[], RetroWork],
        cache: TwoLevelCache,
        model: TextModel,
        prompts: PromptCatalog,
        *,
        model_name: str,
        zone_name: str,
        stars: RetroStars | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._cache = cache
        self._model = model
        self._prompts = prompts
        self._model_name = model_name
        self._zone_name = zone_name
        self._stars = stars
        self._clock = clock or now_utc

    async def meaning(
        self,
        user_id: UUID,
        planet: str,
        start: str,
        end: str,
    ) -> RetroMeaningView:
        clean_planet = planet.strip().casefold()
        if clean_planet not in KNOWN_PLANETS:
            raise FieldInvalid("planet", "errors.validation")

        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        except ValueError as error:
            raise FieldInvalid("period", "errors.date_invalid") from error

        now = self._clock()
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            premium = await uow.subscriptions.has_active(user_id, now)

        zone = profile.timezone or self._zone_name

        owned = False
        if not premium and self._stars is not None:
            subject = retrograde_subject(clean_planet, start)
            owned = await self._stars.owns(user_id, "retrograde", subject)

        access = "allowed" if premium or owned else "stars_required"

        fallback = FALLBACKS.get(
            clean_planet,
            {
                "title": f"Ретроградный {PLANET_NAMES.get(clean_planet, clean_planet)}",
                "body": "Период пересмотра и внутренней концентрации.",
                "advice": "Действуйте осознанно и не торопитесь с важными решениями.",
            },
        )

        if access != "allowed":
            return RetroMeaningView(
                planet=clean_planet,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                access=access,
                price=RETROGRADE_STARS,
                title=fallback["title"],
                body="",
                advice="",
            )

        born = "unknown" if profile.birth_date is None else profile.birth_date.strftime("%d.%m.%Y")
        clock_str = (
            "unknown"
            if profile.birth_time_unknown or profile.birth_time is None
            else profile.birth_time.strftime("%H:%M")
        )
        sun = "unknown" if profile.birth_date is None else calendar_sign(profile.birth_date)
        place = getattr(profile, "birth_place", None) or "unknown"
        facts = facts_text(
            {
                "planet": clean_planet,
                "start": start,
                "end": end,
                "sun": sun,
                "birth_date": born,
                "birth_time": clock_str,
                "birth_place": place,
                "timezone": zone,
            }
        )

        prompt = self._prompts.get("retrograde")
        cache_key = "|".join(
            (
                "retro_meaning",
                clean_planet,
                start,
                end,
                str(prompt.version),
                born,
                clock_str,
                sun,
                place,
                zone,
            )
        )

        expires = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=ZoneInfo(zone))

        async def produce() -> dict[str, object]:
            return await self._generate(user_id, clean_planet, start, end, facts, fallback)

        hit = await self._cache.get_or_create(cache_key, "retrograde", expires, produce)
        data = hit.payload

        return RetroMeaningView(
            planet=clean_planet,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            access="allowed",
            price=RETROGRADE_STARS,
            title=str(data.get("title") or fallback["title"]),
            body=str(data.get("body") or fallback["body"]),
            advice=str(data.get("advice") or fallback["advice"]),
        )

    async def _generate(
        self,
        user_id: UUID,
        planet: str,
        start: str,
        end: str,
        facts: str,
        fallback: dict[str, str],
    ) -> dict[str, object]:
        prompt = self._prompts.get("retrograde")
        user_prompt = (
            prompt.user.replace("{facts}", facts)
            .replace("{planet}", PLANET_NAMES.get(planet, planet))
            .replace("{start}", start)
            .replace("{end}", end)
        )
        repair_prompt = f"{user_prompt}\n{_REPAIR}"

        for text in (user_prompt, repair_prompt):
            parsed = await self._complete(
                user_id, prompt.system, text, prompt.temperature, prompt.max_tokens
            )
            if isinstance(parsed, dict) and "body" in parsed and "title" in parsed:
                return {
                    "title": str(parsed.get("title") or fallback["title"]),
                    "body": str(parsed.get("body") or fallback["body"]),
                    "advice": str(parsed.get("advice") or fallback["advice"]),
                }

        _LOG.warning("retrograde_uses_fallback", model=self._model_name, planet=planet)
        return {
            "title": fallback["title"],
            "body": fallback["body"],
            "advice": fallback["advice"],
        }

    async def _complete(
        self,
        user_id: UUID,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> object | None:
        try:
            reply = await self._model.complete_forecast(
                model=self._model_name,
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
        except Exception as error:
            _LOG.warning(
                "model_call_failed",
                kind="retrograde",
                model=self._model_name,
                error_type=type(error).__name__,
            )
            return None

        async with self._uow_factory() as uow:
            await uow.ai_requests.add(user_id, self._model_name, "retrograde", "ok")
            await uow.commit()

        try:
            return cast(object, json.loads(reply.content))
        except json.JSONDecodeError:
            _LOG.warning("model_reply_rejected", kind="retrograde", model=self._model_name)
            return None
