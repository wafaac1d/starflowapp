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
    assert button.text == "Открыть StarFlow"
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
    assert button.text == "Открыть StarFlow"
    assert button.web_app.url == "https://t.me/starflowapp/bot"
