from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from starflow.bot.handlers import BUTTON_TEXT, WELCOME_MESSAGE, _chat
from starflow.cache.memory import MemoryCache
from starflow.domain.affirmations import AffirmationCard
from starflow.domain.errors import FieldInvalid
from starflow.domain.favorable import FavorableDay
from starflow.domain.privacy import PRIVACY_VERSION
from starflow.domain.records import Profile, RelatedBirth
from starflow.domain.stars import SpendResult, price_of
from starflow.i18n.catalog import Catalog, load_catalog
from starflow.services.affirmations import AffirmationsView
from starflow.services.assistant import AssistantReply
from starflow.services.bot_desk import BotDesk
from starflow.services.chart import ChartView
from starflow.services.favorable import FavorableDetail, FavorableMonth
from starflow.services.forecast import ReadingScope, ReadingView
from starflow.services.profile import DraftInput
from starflow.services.retro import RetroMeaningView
from starflow.services.session import SessionView
from starflow.services.wallet import PremiumPurchase

USER = UUID("00000000-0000-0000-0000-000000000114")
ANNA = UUID("00000000-0000-0000-0000-000000000115")
ROOT = Path(__file__).resolve().parents[2]
_PAID = {
    "week": "week",
    "tomorrow": "tomorrow",
    "month": "month",
    "topics": "topics",
    "synastry": "compatibility",
}


def _catalog() -> Catalog:
    return load_catalog(ROOT / "resources", "ru", MemoryCache(4))


def _clock() -> datetime:
    return datetime(2026, 11, 18, 9, tzinfo=UTC)


async def _sleep(_seconds: float) -> None:
    return None


def _profile(
    *,
    step: str = "done",
    privacy: str | None = PRIVACY_VERSION,
    name: str | None = "Мария",
) -> Profile:
    return Profile(
        id=USER,
        user_id=USER,
        display_name=name,
        birth_date=date(1990, 1, 15) if step == "done" else None,
        birth_time=None,
        birth_time_unknown=True,
        birth_place=None,
        latitude=None,
        longitude=None,
        timezone="Europe/Moscow",
        onboarding_step=step,
        privacy_policy_version=privacy,
    )


class _State:
    def __init__(self, profile: Profile, balance: int = 100) -> None:
        self.profile = profile
        self.premium = False
        self.balance = balance
        self.bought: list[tuple[str, str]] = []
        self.owned: set[tuple[str, str]] = set()
        self.questions: list[str] = []
        self.kinds: list[str] = []
        self.drafts: list[DraftInput] = []


class _Profiles:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def read(self, user_id: UUID) -> tuple[Profile, bool, str | None]:
        del user_id
        sign = "козерог" if self.state.profile.birth_date is not None else None
        return self.state.profile, self.state.premium, sign

    async def accept_privacy(self, user_id: UUID, accepted: bool) -> Profile:
        del user_id, accepted
        self.state.profile = replace(self.state.profile, privacy_policy_version=PRIVACY_VERSION)
        return self.state.profile

    async def continue_draft(self, user_id: UUID, incoming: DraftInput) -> Profile:
        del user_id
        self.state.drafts.append(incoming)
        step = self.state.profile.onboarding_step
        if step in {"welcome", "name"} and incoming.display_name:
            self.state.profile = replace(
                self.state.profile,
                display_name=incoming.display_name,
                onboarding_step="date",
            )
        elif step == "date" and incoming.birth_date:
            self.state.profile = replace(
                self.state.profile,
                birth_date=date(1990, 5, 2),
                onboarding_step="time",
            )
        elif step == "time":
            self.state.profile = replace(
                self.state.profile,
                onboarding_step="done",
                birth_time_unknown=incoming.birth_time_unknown,
                birth_date=date(1990, 5, 2),
            )
        return self.state.profile

    async def skip_place(self, user_id: UUID) -> Profile:
        del user_id
        self.state.profile = replace(self.state.profile, onboarding_step="done")
        return self.state.profile


class _Forecast:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def start(
        self,
        user_id: UUID,
        kind: str,
        idempotency_key: str,
        scope: ReadingScope | None = None,
    ) -> ReadingView:
        del user_id, idempotency_key, scope
        self.state.kinds.append(kind)
        feature = _PAID.get(kind)
        if feature is not None and not any(item[0] == feature for item in self.state.owned):
            return ReadingView(status="stars", body="нужны звёзды")
        title = "День точных решений" if kind == "day" else "Готово"
        return ReadingView(status="ready", title=title, body="Спокойный фон.")

    async def current(
        self,
        user_id: UUID,
        kind: str,
        scope: ReadingScope | None = None,
    ) -> ReadingView:
        del user_id, kind, scope
        return ReadingView(status="ready", title="Готово", body="Спокойный фон.")

    async def related(self, user_id: UUID) -> tuple[RelatedBirth, ...]:
        del user_id
        return (RelatedBirth(ANNA, "Анна", date(1992, 3, 4)),)

    async def referral(self, user_id: UUID) -> tuple[str, str, int, int]:
        del user_id
        return "CODE", "https://t.me/starflowbot?start=ref_CODE", 1, 20


class _Assistant:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def ask(self, user_id: UUID, key: str, question: str) -> AssistantReply:
        del user_id, key
        self.state.questions.append(question)
        return AssistantReply(status="ready", reply="Ответ помощника.")


class _Wallet:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def balance(self, user_id: UUID) -> int:
        del user_id
        return self.state.balance

    async def owns(self, user_id: UUID, feature: str, subject: str) -> bool:
        del user_id
        return (feature, subject) in self.state.owned

    async def buy(self, user_id: UUID, feature: str, subject: str) -> SpendResult:
        del user_id
        self.state.bought.append((feature, subject))
        price = price_of(feature)
        if self.state.balance < price:
            return SpendResult(False, False, self.state.balance, price)
        self.state.balance -= price
        self.state.owned.add((feature, subject))
        return SpendResult(True, True, self.state.balance, price)

    async def redeem_code(self, user_id: UUID, name: str) -> int:
        del user_id
        if name != "ASTRO":
            raise FieldInvalid("code", "errors.gift_invalid")
        self.state.balance += 20
        return self.state.balance

    async def buy_premium(self, user_id: UUID, key: str, price: int, days: int) -> PremiumPurchase:
        del user_id, key, days
        if self.state.balance < price:
            raise FieldInvalid("stars", "errors.stars_required")
        self.state.balance -= price
        self.state.premium = True
        return PremiumPurchase(self.state.balance, True)


class _Chart:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def read(self, user_id: UUID) -> ChartView:
        del user_id
        opened = ("natal", "self") in self.state.owned
        return ChartView(
            sun_sign="козерог",
            sun_sign_source="calendar",
            moon_sign="рак" if opened else None,
            ascendant_sign="лев" if opened else None,
            houses=None,
            planets=(),
            aspects=(),
            transits=(),
            lunar_day=None,
            phase_name=None,
            limitations=(),
            natal_access="allowed" if opened else "stars_required",
            house_cusps=None,
        )


class _Affirmations:
    async def get_affirmations(self, user_id: UUID, category: str) -> AffirmationsView:
        del user_id
        card = AffirmationCard("for_you_1", "Я выбираю свой ритм.", category, "/a.png")
        return AffirmationsView(category, "Для вас", "preview", 0, (card,))


class _Favorable:
    async def month(self, user_id: UUID, month: str, event: str, custom: str) -> FavorableMonth:
        del user_id, custom
        return FavorableMonth(
            "ready",
            event,
            "Встреча",
            month,
            "Europe/Moscow",
            "full",
            0,
            (FavorableDay("2026-11-20", "10:00", "12:00", "Спокойное окно."),),
        )

    async def detail(
        self, user_id: UUID, month: str, event: str, custom: str, day: str
    ) -> FavorableDetail:
        del user_id, month, event, custom, day
        return FavorableDetail("ready", "Встреча", "Подробный фон.", "Не торопитесь.")


class _Retro:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def meaning(self, user_id: UUID, planet: str, start: str, end: str) -> RetroMeaningView:
        del user_id
        opened = any(item[0] == "retrograde" for item in self.state.owned)
        return RetroMeaningView(
            planet,
            start,
            end,
            "allowed" if opened else "stars_required",
            15,
            "Ретроградный Меркурий",
            "Пересмотрите договорённости." if opened else "",
            "Не спешите." if opened else "",
        )


class _Periods:
    async def retrograde_periods(self) -> tuple[tuple[str, str, str], ...]:
        return (("меркурий", "2026-11-01", "2026-11-20"),)


def _desk(state: _State) -> BotDesk:
    return BotDesk(
        _Profiles(state),
        _Forecast(state),
        _Assistant(state),
        _Wallet(state),
        _Chart(state),
        _Affirmations(),
        _Favorable(),
        _Retro(state),
        _Periods(),
        _catalog(),
        zone_name="Europe/Moscow",
        premium_price=250,
        premium_days=30,
        clock=_clock,
        sleep=_sleep,
    )


async def test_menu_lists_text_commands_and_the_app() -> None:
    state = _State(_profile())
    text = await _desk(state).answer(USER, "меню")
    assert "день" in text
    assert "Кнопка ниже открывает приложение" in text
    assert "не обещает точных событий" in text
    assert state.bought == []


async def test_day_is_answered_without_a_charge() -> None:
    state = _State(_profile())
    text = await _desk(state).answer(USER, "день")
    assert "Спокойный фон." in text
    assert "День точных решений" in text
    assert state.bought == []
    assert state.kinds == ["day"]


async def test_paid_reading_waits_for_yes() -> None:
    state = _State(_profile())
    desk = _desk(state)
    offer = await desk.answer(USER, "неделя")
    assert "20" in offer
    assert "Неделя" in offer
    assert state.bought == []
    opened = await desk.answer(USER, "да")
    assert "Спокойный фон." in opened
    assert len(state.bought) == 1
    assert state.bought[0][0] == "week"


async def test_yes_without_a_price_does_not_charge() -> None:
    state = _State(_profile())
    text = await _desk(state).answer(USER, "да")
    assert "день" in text
    assert state.bought == []
    assert state.questions == []


async def test_question_is_charged_only_after_yes() -> None:
    state = _State(_profile())
    desk = _desk(state)
    offer = await desk.answer(USER, "Что мне важно на этой неделе?")
    assert "20" in offer
    assert state.questions == []
    reply = await desk.answer(USER, "да")
    assert reply == "Ответ помощника."
    assert state.questions == ["Что мне важно на этой неделе?"]
    assert state.bought == []


async def test_compatibility_names_the_price_before_the_charge() -> None:
    state = _State(_profile())
    desk = _desk(state)
    offer = await desk.answer(USER, "совместимость Овен и Телец")
    assert "40" in offer
    assert state.bought == []
    opened = await desk.answer(USER, "списать")
    assert "Спокойный фон." in opened
    assert state.bought[0][0] == "compatibility"


async def test_chart_opens_after_confirmation() -> None:
    state = _State(_profile())
    desk = _desk(state)
    offer = await desk.answer(USER, "карта")
    assert "40" in offer
    assert "Луна" not in offer
    opened = await desk.answer(USER, "да")
    assert "Луна: Рак" in opened
    assert state.bought[0] == ("natal", "self")


async def test_short_balance_is_not_spent() -> None:
    state = _State(_profile(), balance=10)
    desk = _desk(state)
    await desk.answer(USER, "завтра")
    text = await desk.answer(USER, "да")
    assert "мало" in text
    assert state.balance == 10
    assert state.owned == set()


async def test_registration_accepts_a_date_and_blocks_commands() -> None:
    state = _State(_profile(step="welcome", privacy=None, name=None))
    desk = _desk(state)
    blocked = await desk.answer(USER, "день")
    assert "Сначала закончим регистрацию" in blocked
    assert "принимаю" in blocked
    assert state.kinds == []
    assert "принимаю" in await desk.answer(USER, "привет")
    assert "Как к вам обращаться" in await desk.answer(USER, "принимаю")
    assert "24.11.1970" in await desk.answer(USER, "Мария")
    assert state.drafts[-1].display_name == "Мария"
    assert "14:30" in await desk.answer(USER, "02051990")
    assert state.drafts[-1].birth_date == "02.05.1990"
    finished = await desk.answer(USER, "не знаю")
    assert "день" in finished
    assert state.profile.onboarding_step == "done"


async def test_balance_code_people_and_retro() -> None:
    state = _State(_profile())
    desk = _desk(state)
    assert "100" in await desk.answer(USER, "баланс")
    assert "120" in await desk.answer(USER, "код ASTRO")
    people = await desk.answer(USER, "близкие")
    assert "Анна" in people
    assert "04.03.1992" in people
    person = await desk.answer(USER, "прогноз Анна")
    assert "Спокойный фон." in person
    assert state.kinds[-1] == "day"
    retro = await desk.answer(USER, "ретроград")
    assert "Меркурий" in retro
    offer = await desk.answer(USER, "ретроград Меркурий")
    assert "15" in offer
    assert state.bought == []
    opened = await desk.answer(USER, "да")
    assert "Пересмотрите договорённости." in opened
    assert state.bought[0][0] == "retrograde"


async def test_favorable_day_and_affirmation_are_text() -> None:
    state = _State(_profile())
    desk = _desk(state)
    day = await desk.answer(USER, "дата встреча")
    assert "2026-11-20" in day
    assert "Спокойное окно." in day
    text = await desk.answer(USER, "аффирмация")
    assert "Я выбираю свой ритм." in text
    assert state.bought == []


class _Sessions:
    def __init__(self, first: bool) -> None:
        self.first = first

    async def accept_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
        language_code: str | None,
        start_param: str | None = None,
    ) -> SessionView:
        del language_code, start_param
        return SessionView(USER, telegram_id, username, False)

    async def mark_bot_welcomed(self, telegram_id: int) -> bool:
        del telegram_id
        return self.first


class _Incoming:
    def __init__(self) -> None:
        self.from_user = _Person()
        self.sent: list[tuple[str, Any]] = []
        self.bot = None

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.sent.append((text, reply_markup))


class _Person:
    id = 7
    username = "maks"
    language_code = "ru"


async def test_chat_reply_keeps_the_open_app_button() -> None:
    state = _State(_profile())
    message = _Incoming()
    await _chat(
        message,  # type: ignore[arg-type]
        _Sessions(False),
        _desk(state),
        _catalog(),
        "https://t.me/starflowapp/bot",
        "день",
    )
    text, markup = message.sent[0]
    assert "Спокойный фон." in text
    assert markup is not None
    button = markup.inline_keyboard[0][0]
    assert button.text == BUTTON_TEXT
    assert button.web_app.url == "https://t.me/starflowapp/bot"

    first = _Incoming()
    await _chat(
        first,  # type: ignore[arg-type]
        _Sessions(True),
        _desk(state),
        _catalog(),
        "https://t.me/starflowapp/bot",
        "меню",
    )
    welcome, _markup = first.sent[0]
    assert welcome.startswith(WELCOME_MESSAGE)
    assert "день" in welcome
