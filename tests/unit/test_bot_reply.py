import pytest

from starflow.bot.handlers import (
    BUTTON_TEXT,
    FOLLOWUP_MESSAGE,
    WELCOME_MESSAGE,
    _open,
    _reply_followup,
    _reply_welcome,
)
from starflow.i18n.catalog import Catalog


class _Message:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup: object = None) -> None:
        self.sent.append((text, reply_markup))


def _catalog() -> Catalog:
    return Catalog(
        "ru",
        {
            "bot.start": "откройте приложение",
            "bot.open": "открыть starflow",
            "bot.start_without_app": "кнопки нет",
        },
    )


@pytest.mark.asyncio
async def test_reply_with_url_carries_a_web_app_button() -> None:
    message = _Message()
    await _open(
        message,
        _catalog(),
        "https://app.example/starflow",
        "",
        "bot.start",
        "bot.start_without_app",
    )
    text, markup = message.sent[0]
    assert text == "откройте приложение"
    assert markup is not None
    button = markup.inline_keyboard[0][0]
    assert button.text == "открыть starflow"
    assert button.web_app is not None
    assert button.web_app.url == "https://app.example/starflow"


@pytest.mark.asyncio
async def test_reply_without_url_explains_where_the_button_will_be() -> None:
    message = _Message()
    await _open(message, _catalog(), "", "", "bot.start", "bot.start_without_app")
    text, markup = message.sent[0]
    assert text == "кнопки нет"
    assert markup is None


@pytest.mark.asyncio
async def test_first_message_sends_welcome_with_app_button() -> None:
    message = _Message()
    message.bot = None
    await _reply_welcome(message, _catalog(), "https://t.me/starflowapp/bot")
    text, markup = message.sent[0]
    assert text == WELCOME_MESSAGE
    assert "Добро пожаловать в обсерваторию" in text
    assert "StarFlow" in text
    assert markup is not None
    button = markup.inline_keyboard[0][0]
    assert button.text == BUTTON_TEXT
    assert button.web_app.url == "https://t.me/starflowapp/bot"


@pytest.mark.asyncio
async def test_subsequent_messages_send_followup_with_app_button() -> None:
    message = _Message()
    await _reply_followup(message, _catalog(), "https://t.me/starflowapp/bot")
    text, markup = message.sent[0]
    assert text == FOLLOWUP_MESSAGE
    assert "Я не отвечаю команды" in text
    assert "StarFlow" in text
    assert markup is not None
    button = markup.inline_keyboard[0][0]
    assert button.text == BUTTON_TEXT
    assert button.web_app.url == "https://t.me/starflowapp/bot"


class _FakeUser:
    def __init__(self, uid: int) -> None:
        self.id = uid


class _FakeSentMsg:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class _MsgWithMessageId:
    def __init__(self, uid: int, msg_id: int) -> None:
        self.from_user = _FakeUser(uid)
        self.sent: list[tuple[str, object]] = []
        self.msg_id = msg_id
        self.bot = None

    async def answer(self, text: str, reply_markup: object = None) -> object:
        self.sent.append((text, reply_markup))
        return _FakeSentMsg(self.msg_id)


@pytest.mark.asyncio
async def test_reply_welcome_and_followup_do_not_replace_the_notice_slot() -> None:
    msg1 = _MsgWithMessageId(1234, 42)
    await _reply_welcome(msg1, _catalog(), "https://t.me/starflowapp/bot")  # type: ignore[arg-type]
    assert msg1.sent

    msg2 = _MsgWithMessageId(1234, 43)
    await _reply_followup(msg2, _catalog(), "https://t.me/starflowapp/bot")  # type: ignore[arg-type]
    assert msg2.sent


class _FakeBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []
        self.sent: list[tuple[int, str, object]] = []
        self.next_msg_id = 100
        self.delete_error: Exception | None = None
        self.send_error: Exception | None = None

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append((chat_id, message_id))
        return True

    async def send_message(self, chat_id: int, text: str, reply_markup: object = None) -> object:
        if self.send_error is not None:
            raise self.send_error
        self.next_msg_id += 1
        self.sent.append((chat_id, text, reply_markup))
        return _FakeSentMsg(self.next_msg_id)


@pytest.mark.asyncio
async def test_bot_runtime_send_notice_deletes_previous_message() -> None:
    from aiogram import Dispatcher
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
    from aiogram.methods import DeleteMessage

    from starflow.bot.runtime import BotRuntime
    from tests.support import make_settings

    fake_bot = _FakeBot()
    settings = make_settings()
    dispatcher = Dispatcher()
    runtime = BotRuntime(settings, fake_bot, dispatcher, (), "menu", _catalog())  # type: ignore[arg-type]

    # 1. First send with explicit previous_message_id
    mid1 = await runtime.send_notice(999, "Hello 1", "", previous_message_id=50)
    assert mid1 == 101
    assert fake_bot.deleted == [(999, 50)]
    assert len(fake_bot.sent) == 1

    # 2. Second send without explicit previous_message_id deletes cached message
    mid2 = await runtime.send_notice(999, "Hello 2", "")
    assert mid2 == 102
    assert fake_bot.deleted == [(999, 50), (999, 101)]

    # 3. Third send: delete_message raises TelegramBadRequest (e.g. message already deleted)
    fake_bot.delete_error = TelegramBadRequest(
        method=DeleteMessage(chat_id=999, message_id=102), message="message not found"
    )
    mid3 = await runtime.send_notice(999, "Hello 3", "")
    assert mid3 == 103
    assert len(fake_bot.sent) == 3

    # 4. A failed delete still sends the new notice.
    fake_bot.delete_error = TelegramForbiddenError(
        method=DeleteMessage(chat_id=999, message_id=103), message="bot was blocked by user"
    )
    mid4 = await runtime.send_notice(999, "Hello 4", "")
    assert mid4 == 104

    fake_bot.delete_error = TelegramRetryAfter(
        method=DeleteMessage(chat_id=999, message_id=104), message="retry", retry_after=7
    )
    mid5 = await runtime.send_notice(999, "Hello 5", "")
    assert mid5 == 105
