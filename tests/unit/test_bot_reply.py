import pytest

from starflow.bot.handlers import _open
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
