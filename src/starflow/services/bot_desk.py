"""Текстовый стол бота. Хендлер только передаёт фразу и отправляет ответ.

Платное действие сначала называет цену. Списание делает кошелёк после «да».
"""

import asyncio
import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from starflow.astro.ecliptic import SIGNS
from starflow.domain.errors import FieldInvalid
from starflow.domain.favorable import favorable_subject
from starflow.domain.privacy import privacy_is_current
from starflow.domain.records import Profile, RelatedBirth
from starflow.domain.stars import (
    SpendResult,
    affirmation_subject,
    current_month_subject,
    current_tomorrow_subject,
    current_week_subject,
    pair_subject,
    price_of,
    retrograde_subject,
)
from starflow.domain.time import now_utc
from starflow.i18n.catalog import Catalog
from starflow.services.affirmations import AffirmationsView
from starflow.services.assistant import AssistantReply
from starflow.services.chart import ChartView
from starflow.services.favorable import FavorableDetail, FavorableMonth
from starflow.services.forecast import ReadingScope, ReadingView
from starflow.services.profile import DraftInput
from starflow.services.retro import KNOWN_PLANETS, PLANET_NAMES, RetroMeaningView
from starflow.services.wallet import PremiumPurchase

_POLLS = 20
_PAUSE = 0.8
_LIMIT = 3800
_PARTIAL = frozenset({"time_unknown", "place_missing", "birth_date_missing", "timezone_missing"})
_MENU = frozenset({"меню", "помощь", "help", "start", "команды", "открыть", "открыть starflow"})
_BALANCE = frozenset({"баланс", "звезды", "счет"})
_PROFILE = frozenset({"профиль", "profile"})
_SETTINGS = frozenset({"настройки", "settings"})
_TERMS = frozenset({"условия", "terms"})
_SUPPORT = frozenset({"поддержка", "paysupport"})
_PREMIUM = frozenset({"premium", "премиум"})
_BUY = frozenset({"подключить"})
_REFERRAL = frozenset({"пригласить", "реферал", "приглашение"})
_PEOPLE = frozenset({"близкие", "люди"})
_DAY = frozenset({"день", "сегодня", "прогноз"})
_TOMORROW = frozenset({"завтра", "на завтра", "прогноз на завтра"})
_WEEK = frozenset({"неделя", "на неделю", "прогноз на неделю"})
_MONTH = frozenset({"месяц", "на месяц"})
_MOON = frozenset({"луна", "лунный фон"})
_ADVICE = frozenset({"совет"})
_CHART = frozenset({"карта", "натальная", "натальная карта", "моя карта"})
_RETRO = frozenset({"ретроград", "ретроградные", "ретро"})
_ACCEPT = frozenset({"принимаю", "согласен", "согласна", "принято"})
_UNKNOWN_TIME = frozenset({"не знаю", "неизвестно", "пропустить", "нет"})
_SKIP_PLACE = frozenset({"пропустить", "готово", "без места"})
_YES = frozenset({"да", "списать"})
_AFFIRM = {
    "аффирмация": "for_you",
    "аффирмации": "for_you",
    "аффирмация для вас": "for_you",
    "аффирмация уверенность": "confidence",
    "аффирмация спокойствие": "calm",
}
_TOPICS = {
    "любовь": "отношения",
    "отношения": "отношения",
    "работа": "работа",
    "здоровье": "эмоциональное состояние",
    "финансы": "финансы",
}
_TOPIC_LABEL = {
    "отношения": "Любовь",
    "работа": "Работа",
    "финансы": "Финансы",
    "эмоциональное состояние": "Здоровье",
}
_FOCUS = (
    ("общие ориентиры", "values"),
    ("ориентиры", "values"),
    ("диалог", "dialog"),
    ("эмоции", "emotions"),
)
_FOCUS_LABEL = {
    "dialog": "Диалог",
    "emotions": "Эмоции",
    "values": "Общие ориентиры",
}
_FAVOR = (
    ("встреч", "meeting"),
    ("поездк", "trip"),
    ("покупк", "purchase"),
)
_PROMPTS = {
    "welcome": "bot.ask_name",
    "name": "bot.ask_name",
    "date": "bot.ask_date",
    "time": "bot.ask_time",
    "timezone": "bot.ask_zone",
    "place": "bot.ask_place",
    "done": "bot.chat_menu",
}


class DeskReply(str):
    """Текст ответа. advance удаляет прошлый шаг, track запоминает новый вопрос."""

    advance: bool
    track: bool

    def __new__(
        cls,
        text: str,
        advance: bool = False,
        track: bool = False,
    ) -> "DeskReply":
        reply = str.__new__(cls, text)
        reply.advance = advance
        reply.track = track
        return reply


@dataclass(frozen=True)
class _Intent:
    name: str
    left: str = ""
    right: str = ""
    topic: str = ""
    event: str = ""
    custom: str = ""
    category: str = ""
    planet: str = ""
    person: str = ""
    code: str = ""
    day: str = ""


@dataclass(frozen=True)
class _Hold:
    action: str
    feature: str
    subject: str
    title: str
    kind: str = ""
    topic: str = ""
    left: str = ""
    right: str = ""
    related: str = ""
    category: str = ""
    month: str = ""
    event: str = ""
    custom: str = ""
    planet: str = ""
    start: str = ""
    end: str = ""
    question: str = ""


class DeskProfile(Protocol):
    async def read(self, user_id: UUID) -> tuple[Profile, bool, str | None]: ...

    async def accept_privacy(self, user_id: UUID, accepted: bool) -> Profile: ...

    async def continue_draft(self, user_id: UUID, incoming: DraftInput) -> Profile: ...

    async def skip_place(self, user_id: UUID) -> Profile: ...


class DeskForecast(Protocol):
    async def start(
        self,
        user_id: UUID,
        kind: str,
        idempotency_key: str,
        scope: ReadingScope | None = None,
    ) -> ReadingView: ...

    async def current(
        self,
        user_id: UUID,
        kind: str,
        scope: ReadingScope | None = None,
    ) -> ReadingView: ...

    async def related(self, user_id: UUID) -> tuple[RelatedBirth, ...]: ...

    async def referral(self, user_id: UUID) -> tuple[str, str, int, int]: ...


class DeskAssistant(Protocol):
    async def ask(self, user_id: UUID, key: str, question: str) -> AssistantReply: ...


class DeskWallet(Protocol):
    async def balance(self, user_id: UUID) -> int: ...

    async def owns(self, user_id: UUID, feature: str, subject: str) -> bool: ...

    async def buy(self, user_id: UUID, feature: str, subject: str) -> SpendResult: ...

    async def redeem_code(self, user_id: UUID, name: str) -> int: ...

    async def buy_premium(
        self, user_id: UUID, key: str, price: int, days: int
    ) -> PremiumPurchase: ...


class DeskChart(Protocol):
    async def read(self, user_id: UUID) -> ChartView: ...


class DeskAffirmations(Protocol):
    async def get_affirmations(self, user_id: UUID, category: str) -> AffirmationsView: ...


class DeskFavorable(Protocol):
    async def month(self, user_id: UUID, month: str, event: str, custom: str) -> FavorableMonth: ...

    async def detail(
        self, user_id: UUID, month: str, event: str, custom: str, day: str
    ) -> FavorableDetail: ...


class DeskRetro(Protocol):
    async def meaning(
        self, user_id: UUID, planet: str, start: str, end: str
    ) -> RetroMeaningView: ...


class DeskPeriods(Protocol):
    async def retrograde_periods(self) -> tuple[tuple[str, str, str], ...]: ...


class BotDesk:
    def __init__(
        self,
        profile: DeskProfile,
        forecast: DeskForecast,
        assistant: DeskAssistant,
        wallet: DeskWallet,
        chart: DeskChart,
        affirmations: DeskAffirmations,
        favorable: DeskFavorable,
        retro: DeskRetro,
        periods: DeskPeriods,
        catalog: Catalog,
        *,
        zone_name: str,
        premium_price: int,
        premium_days: int,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._profile = profile
        self._forecast = forecast
        self._assistant = assistant
        self._wallet = wallet
        self._chart_service = chart
        self._affirmations = affirmations
        self._favorable_service = favorable
        self._retro_service = retro
        self._periods = periods
        self._catalog = catalog
        self._zone = zone_name
        self._premium_price = premium_price
        self._premium_days = premium_days
        self._clock = clock or now_utc
        self._sleep = sleep or _pause
        self._pending: dict[UUID, _Hold] = {}
        self._pairs: dict[UUID, tuple[str, str]] = {}
        self._events: dict[UUID, tuple[str, str, str]] = {}

    async def answer(self, user_id: UUID, text: str, *, opening: bool = False) -> DeskReply:
        try:
            reply = await self._answer(user_id, text, opening=opening)
        except FieldInvalid as error:
            reply = DeskReply(self._known(error.message_key, "bot.reading_error"))
        return DeskReply(_clip(reply), reply.advance, reply.track)

    async def _answer(self, user_id: UUID, text: str, *, opening: bool) -> DeskReply:
        raw = text.strip()
        if raw.startswith("/"):
            raw = raw[1:].strip()
        profile, premium, _sign = await self._profile.read(user_id)
        if opening and _registered(profile):
            return DeskReply(await self._home(user_id))
        if not _registered(profile):
            return await self._registration(user_id, profile, raw, opening=opening)
        if raw == "":
            return DeskReply(self._text("bot.chat_menu"))
        folded = _fold(raw)
        if folded in _YES:
            hold = self._pending.pop(user_id, None)
            if hold is None:
                return DeskReply(self._text("bot.chat_menu"))
            return DeskReply(await self._confirm(user_id, hold))
        intent = _intent(raw)
        if intent is None:
            return DeskReply(await self._assistant_offer(user_id, raw, premium))
        self._pending.pop(user_id, None)
        return DeskReply(await self._dispatch(user_id, intent, premium))

    async def _registration(
        self,
        user_id: UUID,
        profile: Profile,
        raw: str,
        *,
        opening: bool,
    ) -> DeskReply:
        if opening or raw == "":
            return DeskReply(self._prompt(profile), track=True)
        if _intent(raw) is not None:
            pending = f"{self._text('bot.step_pending')}\n\n{self._prompt(profile)}"
            return DeskReply(pending)
        before_step = profile.onboarding_step
        before_privacy = profile.privacy_policy_version
        body = await self._draft(user_id, profile, raw)
        current, _premium, _sign = await self._profile.read(user_id)
        moved = (
            current.onboarding_step != before_step
            or current.privacy_policy_version != before_privacy
        )
        if moved and _registered(current):
            body = await self._home(user_id)
        return DeskReply(body, advance=moved, track=moved and not _registered(current))

    async def _draft(self, user_id: UUID, profile: Profile, raw: str) -> str:
        folded = _fold(raw)
        if not privacy_is_current(profile.privacy_policy_version):
            if folded not in _ACCEPT:
                return self._text("bot.ask_privacy")
            await self._profile.accept_privacy(user_id, True)
            return self._text("bot.ask_name")
        step = profile.onboarding_step
        try:
            updated = await self._advance(user_id, step, raw, folded)
        except FieldInvalid as error:
            return self._known(error.message_key, _PROMPTS.get(step, "bot.ask_name"))
        return self._prompt(updated)

    async def _advance(self, user_id: UUID, step: str, raw: str, folded: str) -> Profile:
        if step in {"welcome", "name"}:
            return await self._profile.continue_draft(
                user_id, DraftInput(raw.strip(), None, None, False, None)
            )
        if step == "date":
            return await self._profile.continue_draft(
                user_id, DraftInput(None, _date_text(raw), None, False, None)
            )
        if step == "time":
            unknown = folded in _UNKNOWN_TIME
            clock = None if unknown else _time_text(raw)
            return await self._profile.continue_draft(
                user_id, DraftInput(None, None, clock, unknown, None)
            )
        if step == "timezone":
            zone = self._zone if folded in _SKIP_PLACE or folded in _UNKNOWN_TIME else raw.strip()
            return await self._profile.continue_draft(
                user_id, DraftInput(None, None, None, False, zone)
            )
        if step == "place":
            if folded not in _SKIP_PLACE:
                raise FieldInvalid("birth_place", "bot.ask_place")
            return await self._profile.skip_place(user_id)
        raise FieldInvalid("step", "bot.ask_name")

    async def _confirm(self, user_id: UUID, hold: _Hold) -> str:
        if hold.action == "assistant":
            return await self._ask(user_id, hold.subject, hold.question)
        if hold.action == "premium":
            return await self._buy_premium(user_id, hold)
        try:
            result = await self._wallet.buy(user_id, hold.feature, hold.subject)
        except FieldInvalid as error:
            return self._known(error.message_key, "bot.reading_error")
        if not result.allowed:
            return self._format("bot.price_short", balance=result.balance)
        return await self._rerun(user_id, hold)

    async def _buy_premium(self, user_id: UUID, hold: _Hold) -> str:
        try:
            bought = await self._wallet.buy_premium(
                user_id, hold.subject, self._premium_price, self._premium_days
            )
        except FieldInvalid:
            balance = await self._wallet.balance(user_id)
            return self._format("bot.price_short", balance=balance)
        return self._format("bot.premium_bought", balance=bought.balance)

    async def _rerun(self, user_id: UUID, hold: _Hold) -> str:
        if hold.action == "reading":
            related = UUID(hold.related) if hold.related else None
            scope = ReadingScope(
                topic=hold.topic,
                left_sign=hold.left,
                right_sign=hold.right,
                related_id=related,
            )
            return await self._reading(
                user_id, hold.kind, scope, hold.title, hold.feature, hold.subject, True
            )
        if hold.action == "chart":
            return await self._chart(user_id, True)
        if hold.action == "affirmation":
            return await self._affirmation(user_id, hold.category, True)
        if hold.action == "favorable":
            return await self._favorable(user_id, hold.event, hold.custom, True)
        if hold.action == "retro":
            return await self._retro(user_id, hold.planet, True)
        return self._text("bot.reading_error")

    async def _dispatch(self, user_id: UUID, intent: _Intent, premium: bool) -> str:
        name = intent.name
        if name == "menu":
            return self._text("bot.chat_menu")
        if name == "balance":
            return await self._balance(user_id)
        if name == "code":
            return await self._code(user_id, intent.code)
        if name == "profile":
            return await self._profile_text(user_id)
        if name == "settings":
            return self._text("bot.settings")
        if name == "terms":
            return self._text("bot.terms")
        if name == "support":
            return self._text("bot.paysupport")
        if name == "premium":
            return await self._premium_status(user_id)
        if name == "premium_buy":
            return await self._premium_offer(user_id)
        if name == "referral":
            return await self._referral(user_id)
        if name == "people":
            return await self._people(user_id)
        if name == "person":
            return await self._person(user_id, intent.person)
        if name == "day":
            return await self._open(user_id, "day", "Сегодня")
        if name == "tomorrow":
            return await self._priced_period(user_id, "tomorrow", "Завтра")
        if name == "week":
            return await self._priced_period(user_id, "week", "Неделя")
        if name == "month":
            return await self._priced_period(user_id, "month", "Месяц")
        if name == "moon":
            return await self._open(user_id, "moon", "Луна")
        if name == "advice":
            return await self._open(user_id, "advice", "Совет")
        if name == "topic":
            return await self._topic(user_id, intent.topic)
        if name == "chart":
            return await self._chart(user_id, False)
        if name == "compatibility":
            return await self._compat(user_id, intent.left, intent.right, "")
        if name == "focus":
            return await self._compat(user_id, intent.left, intent.right, intent.topic)
        if name == "affirmation":
            return await self._affirmation(user_id, intent.category, False)
        if name == "favorable":
            return await self._favorable(user_id, intent.event, intent.custom, False)
        if name == "detail":
            return await self._detail(user_id, intent.day, premium)
        if name == "retro":
            return await self._retro_list()
        if name == "retro_planet":
            return await self._retro(user_id, intent.planet, False)
        return self._text("bot.chat_menu")

    async def _open(self, user_id: UUID, kind: str, title: str) -> str:
        return await self._reading(user_id, kind, ReadingScope(), title, "", "", False)

    async def _priced_period(self, user_id: UUID, kind: str, title: str) -> str:
        moment = self._clock()
        if kind == "tomorrow":
            subject = current_tomorrow_subject(moment, self._zone)
        elif kind == "month":
            subject = current_month_subject(moment, self._zone)
        else:
            subject = current_week_subject(moment, self._zone)
        return await self._reading(user_id, kind, ReadingScope(), title, kind, subject, False)

    async def _topic(self, user_id: UUID, topic: str) -> str:
        title = _TOPIC_LABEL.get(topic, _cap(topic))
        subject = current_week_subject(self._clock(), self._zone)
        return await self._reading(
            user_id,
            "topics",
            ReadingScope(topic=topic),
            title,
            "topics",
            subject,
            False,
        )

    async def _compat(self, user_id: UUID, left: str, right: str, topic: str) -> str:
        if left == "" or right == "":
            stored = self._pairs.get(user_id)
            if stored is None:
                key = "bot.compat_need" if topic else "bot.compat_hint"
                return self._text(key)
            left, right = stored
        self._pairs[user_id] = (left, right)
        try:
            subject = pair_subject(left, right)
        except ValueError:
            return self._text("bot.compat_hint")
        label = _FOCUS_LABEL.get(topic, "")
        title = f"Совместимость {_cap(left)} и {_cap(right)}"
        if label != "":
            title = f"{label}. {title}"
        return await self._reading(
            user_id,
            "synastry",
            ReadingScope(topic=topic, left_sign=left, right_sign=right),
            title,
            "compatibility",
            subject,
            False,
        )

    async def _reading(
        self,
        user_id: UUID,
        kind: str,
        scope: ReadingScope,
        title: str,
        feature: str,
        subject: str,
        paid: bool,
    ) -> str:
        extra = f"{scope.topic}{scope.left_sign}{scope.right_sign}"
        if scope.related_id is not None:
            extra = f"{extra}{scope.related_id.hex}"
        view = await self._poll(user_id, kind, scope, extra, paid)
        if view.status == "stars" and not paid and feature != "":
            return self._remember(
                user_id,
                _Hold(
                    "reading",
                    feature,
                    subject,
                    title,
                    kind=kind,
                    topic=scope.topic,
                    left=scope.left_sign,
                    right=scope.right_sign,
                    related="" if scope.related_id is None else str(scope.related_id),
                ),
            )
        return self._format_reading(view, title, kind, scope.topic)

    async def _poll(
        self,
        user_id: UUID,
        kind: str,
        scope: ReadingScope,
        extra: str,
        paid: bool,
    ) -> ReadingView:
        key = self._reading_key(user_id, kind, extra, paid)
        view = await self._forecast.start(user_id, kind, key, scope)
        for _ in range(_POLLS):
            if view.status != "pending":
                return view
            await self._sleep(_PAUSE)
            view = await self._forecast.current(user_id, kind, scope)
        return view

    async def _chart(self, user_id: UUID, paid: bool) -> str:
        view = await self._chart_service.read(user_id)
        if view.natal_access == "stars_required" and not paid:
            return self._remember(user_id, _Hold("chart", "natal", "self", "Натальная карта"))
        if view.natal_access != "allowed":
            if view.natal_access == "stars_required":
                return self._text("bot.reading_error")
            return self._text("bot.premium_only")
        return self._format_chart(view)

    async def _affirmation(self, user_id: UUID, category: str, paid: bool) -> str:
        view = await self._affirmations.get_affirmations(user_id, category)
        if view.access == "locked" and not paid:
            return self._remember(
                user_id,
                _Hold(
                    "affirmation",
                    "affirmation",
                    affirmation_subject(category),
                    view.label,
                    category=category,
                ),
            )
        if paid and view.access == "locked":
            return self._text("bot.reading_error")
        lines = [view.label, *(card.text for card in view.cards)]
        return _clip("\n\n".join(line for line in lines if line))

    async def _favorable(self, user_id: UUID, event: str, custom: str, paid: bool) -> str:
        if event == "":
            return self._text("bot.favorable_need")
        month = self._month()
        try:
            subject = favorable_subject(month, event, custom)
            view = await self._favorable_service.month(user_id, month, event, custom)
        except FieldInvalid as error:
            return self._known(error.message_key, "bot.favorable_need")
        self._events[user_id] = (month, event, custom)
        if view.access == "locked" and not paid:
            label = view.free_chosen_label or view.label
            self._pending[user_id] = _Hold(
                "favorable",
                "favorable",
                subject,
                view.label,
                month=month,
                event=event,
                custom=custom,
            )
            price = view.price or price_of("favorable")
            return self._format("bot.favorable_locked", label=label, price=price)
        if paid and view.access == "locked":
            return self._text("bot.reading_error")
        return self._favorable_text(user_id, view, subject, month, event, custom, paid)

    def _favorable_text(
        self,
        user_id: UUID,
        view: FavorableMonth,
        subject: str,
        month: str,
        event: str,
        custom: str,
        paid: bool,
    ) -> str:
        if view.status != "ready" and not view.days:
            return self._text("bot.reading_error")
        lines = [view.label]
        lines.extend(f"{day.date}, {day.start}-{day.end}. {day.note}" for day in view.days)
        if view.access == "preview" and view.price > 0 and not paid:
            self._pending[user_id] = _Hold(
                "favorable",
                "favorable",
                subject,
                view.label,
                month=month,
                event=event,
                custom=custom,
            )
            lines.append(self._format("bot.price_ask", title=view.label, price=view.price))
        return _clip("\n\n".join(line for line in lines if line))

    async def _detail(self, user_id: UUID, day: str, premium: bool) -> str:
        stored = self._events.get(user_id)
        if stored is None:
            return self._text("bot.favorable_need")
        if not premium:
            return self._text("bot.premium_only")
        month, event, custom = stored
        try:
            found = await self._favorable_service.detail(user_id, month, event, custom, day)
        except FieldInvalid as error:
            return self._known(error.message_key, "bot.reading_error")
        if found.access != "ready":
            return self._text("bot.premium_only")
        parts = (found.title, found.body, found.advice)
        return _clip("\n\n".join(part for part in parts if part))

    async def _retro_list(self) -> str:
        periods = await self._periods.retrograde_periods()
        if not periods:
            return f"{self._text('bot.retro_none')}\n\n{self._text('bot.retro_hint')}"
        lines = [self._text("bot.retro_list")]
        for planet, start, end in periods:
            name = _cap(PLANET_NAMES.get(planet, planet))
            lines.append(f"{name}: {start} — {end}")
        lines.append(self._text("bot.retro_hint"))
        return "\n".join(lines)

    async def _retro(self, user_id: UUID, planet: str, paid: bool) -> str:
        periods = await self._periods.retrograde_periods()
        match = next((item for item in periods if item[0] == planet), None)
        if match is None:
            return self._text("bot.retro_none")
        _planet, start, end = match
        view = await self._retro_service.meaning(user_id, planet, start, end)
        if view.access != "allowed" and not paid:
            return self._remember(
                user_id,
                _Hold(
                    "retro",
                    "retrograde",
                    retrograde_subject(planet, start),
                    view.title,
                    planet=planet,
                    start=start,
                    end=end,
                ),
            )
        if view.access != "allowed":
            return self._text("bot.reading_error")
        parts = (view.title, view.body, view.advice)
        return _clip("\n\n".join(part for part in parts if part))

    async def _assistant_offer(self, user_id: UUID, question: str, premium: bool) -> str:
        key = _question_key(question)
        if premium or await self._wallet.owns(user_id, "assistant", key):
            return await self._ask(user_id, key, question)
        self._pending[user_id] = _Hold("assistant", "assistant", key, "Вопрос", question=question)
        return self._format("bot.price_ask", title="Вопрос", price=price_of("assistant"))

    async def _ask(self, user_id: UUID, key: str, question: str) -> str:
        try:
            reply = await self._assistant.ask(user_id, key, question)
        except FieldInvalid as error:
            return self._known(error.message_key, "bot.reading_error")
        if reply.reply:
            return reply.reply
        if reply.status == "stars":
            balance = await self._wallet.balance(user_id)
            return self._format("bot.price_short", balance=balance)
        if reply.status == "premium":
            return self._text("bot.premium_only")
        if reply.status == "limit":
            return self._text("bot.limit_hit")
        return self._text("bot.reading_error")

    async def _premium_status(self, user_id: UUID) -> str:
        _profile, premium, _sign = await self._profile.read(user_id)
        state = "bot.premium_on" if premium else "bot.premium_off"
        return f"Premium\n\n{self._text(state)}\n\n{self._text('bot.premium')}"

    async def _premium_offer(self, user_id: UUID) -> str:
        _profile, premium, _sign = await self._profile.read(user_id)
        if premium:
            return self._text("bot.premium_on")
        key = self._premium_key(user_id)
        self._pending[user_id] = _Hold("premium", "premium", key, "Premium")
        return self._format("bot.premium_ask", days=self._premium_days, price=self._premium_price)

    async def _people(self, user_id: UUID) -> str:
        rows = await self._forecast.related(user_id)
        if not rows:
            return self._text("bot.people_empty")
        lines = [self._text("bot.people_head"), ""]
        for person in rows:
            born = (
                "без даты" if person.birth_date is None else person.birth_date.strftime("%d.%m.%Y")
            )
            lines.append(f"{person.display_name}\n{born}\n")
        lines.append(self._text("bot.people_hint"))
        return "\n".join(lines)

    async def _person(self, user_id: UUID, name: str) -> str:
        rows = await self._forecast.related(user_id)
        folded = _fold(name)
        match = next((item for item in rows if _fold(item.display_name) == folded), None)
        if match is None:
            return self._text("bot.person_missing")
        return await self._reading(
            user_id,
            "day",
            ReadingScope(related_id=match.id),
            match.display_name,
            "",
            "",
            False,
        )

    async def _balance(self, user_id: UUID) -> str:
        amount = await self._wallet.balance(user_id)
        return self._format("bot.balance_line", balance=amount)

    async def _code(self, user_id: UUID, name: str) -> str:
        try:
            amount = await self._wallet.redeem_code(user_id, name)
        except FieldInvalid as error:
            return self._known(error.message_key, "errors.gift_invalid")
        return self._format("bot.code_ok", balance=amount)

    async def _home(self, user_id: UUID) -> str:
        profile, _premium, _sign = await self._profile.read(user_id)
        name = profile.display_name or "Здравствуйте"
        card = await self._profile_text(user_id)
        lead = self._format("bot.home_ready", name=name)
        return f"{lead}\n\n{card}\n\n{self._text('bot.home_hint')}"

    async def _profile_text(self, user_id: UUID) -> str:
        profile, premium, sign = await self._profile.read(user_id)
        if not _registered(profile):
            return self._prompt(profile)
        name = profile.display_name or "—"
        born = (
            "дата не указана"
            if profile.birth_date is None
            else profile.birth_date.strftime("%d.%m.%Y")
        )
        if profile.birth_time_unknown or profile.birth_time is None:
            clock = "не указано"
        else:
            clock = profile.birth_time.strftime("%H:%M")
        state = self._text("bot.premium_on" if premium else "bot.premium_off")
        balance = await self._wallet.balance(user_id)
        return self._format(
            "bot.profile_card",
            name=name,
            date=born,
            time=clock,
            place=profile.birth_place or "не указано",
            sign=sign or "—",
            premium=state,
            balance=balance,
        )

    async def _referral(self, user_id: UUID) -> str:
        _code, link, count, earned = await self._forecast.referral(user_id)
        return self._format("bot.referral_line", link=link, count=count, earned=earned)

    def _format_reading(self, view: ReadingView, title: str, kind: str, topic: str) -> str:
        if view.status == "pending":
            return self._text("bot.reading_wait")
        if view.status == "premium":
            return self._text("bot.premium_only")
        if view.status == "limit":
            return self._text("bot.limit_hit")
        if view.status != "ready":
            return view.body or self._text("bot.reading_error")
        parts: list[str] = [title]
        if kind != "topics" and view.title and view.title != title:
            parts.append(view.title)
        if view.body:
            parts.append(view.body)
        for line in view.topics.values():
            if line and line not in parts:
                parts.append(line)
        if _PARTIAL.intersection(view.limitations):
            parts.append(self._text("bot.reading_partial"))
        if kind == "synastry" and topic == "":
            parts.append(self._text("bot.compat_more"))
        return _clip("\n\n".join(parts))

    def _format_chart(self, view: ChartView) -> str:
        parts = ["Натальная карта", ""]
        if view.sun_sign:
            parts.append(f"Солнце: {_cap(view.sun_sign)}")
        if view.moon_sign:
            parts.append(f"Луна: {_cap(view.moon_sign)}")
        if view.ascendant_sign:
            parts.append(f"Асцендент: {_cap(view.ascendant_sign)}")
        if view.phase_name:
            parts.append(view.phase_name)
        for planet in view.planets:
            if planet.sign is None:
                continue
            mark = ", ретроград" if planet.retrograde else ""
            parts.append(f"{_cap(planet.name)}: {_cap(planet.sign)}{mark}")
        if _PARTIAL.intersection(view.limitations):
            parts.append("")
            parts.append(self._text("bot.chart_partial"))
        return _clip("\n".join(parts))

    def _remember(self, user_id: UUID, hold: _Hold) -> str:
        self._pending[user_id] = hold
        return self._format("bot.price_ask", title=hold.title, price=price_of(hold.feature))

    def _prompt(self, profile: Profile) -> str:
        if not privacy_is_current(profile.privacy_policy_version):
            return self._text("bot.ask_privacy")
        return self._text(_PROMPTS.get(profile.onboarding_step, "bot.ask_name"))

    def _reading_key(self, user_id: UUID, kind: str, extra: str, paid: bool) -> str:
        moment = self._clock().astimezone(ZoneInfo(self._zone))
        flag = "p" if paid else "o"
        raw = f"bot{flag}{kind}{moment.date().strftime('%Y%m%d')}{extra}{user_id.hex[:8]}"
        cleaned = "".join(
            character for character in raw if character.isalnum() or character in "_-"
        )
        if len(cleaned) < 8:
            cleaned = f"bot{flag}{user_id.hex[:12]}"
        return cleaned[:80]

    def _premium_key(self, user_id: UUID) -> str:
        stamp = str(int(self._clock().timestamp()))
        return f"botprem{user_id.hex[:8]}{stamp}"[:80]

    def _month(self) -> str:
        local = self._clock().astimezone(ZoneInfo(self._zone))
        return f"{local.year:04d}-{local.month:02d}"

    def _text(self, key: str) -> str:
        return self._catalog.text(key)

    def _format(self, key: str, **values: str | int) -> str:
        return self._catalog.format(key, **values)

    def _known(self, key: str, fallback: str) -> str:
        try:
            return self._catalog.text(key)
        except KeyError:
            return self._catalog.text(fallback)


def _registered(profile: Profile) -> bool:
    return profile.onboarding_step == "done" and privacy_is_current(profile.privacy_policy_version)


def _fold(value: str) -> str:
    return " ".join(value.strip().casefold().replace("ё", "е").split())


def _intent(raw: str) -> _Intent | None:
    folded = _fold(raw)
    named = _named(folded)
    if named is not None:
        return named
    if folded.startswith("код "):
        return _Intent("code", code=raw.strip().split(None, 1)[1].strip())
    if folded.startswith("подробнее "):
        return _Intent("detail", day=_iso_day(folded.split(None, 1)[1]))
    if folded.startswith("прогноз "):
        return _Intent("person", person=raw.strip().split(None, 1)[1].strip())
    if folded.startswith("тема "):
        found = _TOPICS.get(folded.split(None, 1)[1])
        if found is not None:
            return _Intent("topic", topic=found)
    affirmation = _affirmation_intent(folded)
    if affirmation is not None:
        return affirmation
    if folded in _RETRO:
        return _Intent("retro")
    if "ретро" in folded:
        planet = _planet(folded)
        if planet is not None:
            return _Intent("retro_planet", planet=planet)
    favorable = _favorable_intent(raw, folded)
    if favorable is not None:
        return favorable
    pair = _pair(folded)
    focus = _focus_intent(folded, pair)
    if focus is not None:
        return focus
    if "совместим" in folded or folded == "пара" or folded.startswith("пара "):
        if pair is None:
            return _Intent("compatibility")
        return _Intent("compatibility", left=pair[0], right=pair[1])
    return None


def _named(folded: str) -> _Intent | None:
    if folded in _MENU:
        return _Intent("menu")
    if folded in _BALANCE:
        return _Intent("balance")
    if folded in _PROFILE:
        return _Intent("profile")
    if folded in _SETTINGS:
        return _Intent("settings")
    if folded in _TERMS:
        return _Intent("terms")
    if folded in _SUPPORT:
        return _Intent("support")
    if folded in _PREMIUM:
        return _Intent("premium")
    if folded in _BUY:
        return _Intent("premium_buy")
    if folded in _REFERRAL:
        return _Intent("referral")
    if folded in _PEOPLE:
        return _Intent("people")
    if folded in _TOMORROW:
        return _Intent("tomorrow")
    if folded in _WEEK:
        return _Intent("week")
    if folded in _MONTH:
        return _Intent("month")
    if folded in _MOON:
        return _Intent("moon")
    if folded in _ADVICE:
        return _Intent("advice")
    if folded in _CHART:
        return _Intent("chart")
    if folded in _DAY:
        return _Intent("day")
    if folded in _TOPICS:
        return _Intent("topic", topic=_TOPICS[folded])
    return None


def _affirmation_intent(folded: str) -> _Intent | None:
    category = _AFFIRM.get(folded)
    if category is not None:
        return _Intent("affirmation", category=category)
    if folded.startswith("аффирмация ") or folded.startswith("аффирмации "):
        if "уверен" in folded:
            return _Intent("affirmation", category="confidence")
        if "спокой" in folded:
            return _Intent("affirmation", category="calm")
        return _Intent("affirmation", category="for_you")
    return None


def _favorable_intent(raw: str, folded: str) -> _Intent | None:
    triggered = (
        folded.startswith("дата ")
        or folded.startswith("благоприят")
        or folded in {"встреча", "поездка", "покупка"}
        or folded.startswith("свой ")
    )
    if not triggered:
        return None
    if "свой" in folded:
        index = folded.find("свой")
        custom = raw.strip()[index + len("свой") :].strip()
        return _Intent("favorable", event="custom", custom=custom)
    for needle, event in _FAVOR:
        if needle in folded:
            return _Intent("favorable", event=event)
    return _Intent("favorable")


def _focus_intent(folded: str, pair: tuple[str, str] | None) -> _Intent | None:
    for word, code in _FOCUS:
        exact = folded == word
        with_signs = folded.startswith(f"{word} ") and pair is not None
        if not exact and not with_signs:
            continue
        if pair is None:
            return _Intent("focus", topic=code)
        return _Intent("focus", topic=code, left=pair[0], right=pair[1])
    return None


def _planet(folded: str) -> str | None:
    for planet in sorted(KNOWN_PLANETS, key=len, reverse=True):
        if re.search(rf"(?<!\w){planet}(?!\w)", folded):
            return planet
    return None


def _pair(folded: str) -> tuple[str, str] | None:
    found: list[str] = []
    for sign in sorted(SIGNS, key=len, reverse=True):
        if re.search(rf"(?<!\w){sign}(?!\w)", folded):
            found.append(sign)
        if len(found) == 2:
            break
    if len(found) < 2:
        return None
    return found[0], found[1]


def _date_text(raw: str) -> str:
    compact = raw.strip().replace(" ", "")
    if re.fullmatch(r"\d{8}", compact):
        return f"{compact[:2]}.{compact[2:4]}.{compact[4:]}"
    return raw.strip()


def _time_text(raw: str) -> str:
    compact = raw.strip().replace(" ", "")
    if re.fullmatch(r"\d{4}", compact):
        return f"{compact[:2]}:{compact[2:]}"
    return raw.strip()


def _iso_day(value: str) -> str:
    parts = value.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        day, month, year = parts
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return value


def _question_key(question: str) -> str:
    digest = hashlib.sha256(question.casefold().strip().encode()).hexdigest()[:20]
    return f"botq{digest}"


def _cap(value: str) -> str:
    if value == "":
        return value
    return value[0].upper() + value[1:]


def _clip(text: str) -> str:
    if len(text) <= _LIMIT:
        return text
    return text[: _LIMIT - 1].rstrip() + "…"


async def _pause(seconds: float) -> None:
    await asyncio.sleep(seconds)
