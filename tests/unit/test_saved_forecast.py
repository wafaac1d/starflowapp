"""Сохранённый прогноз открывается только из избранного своего владельца."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from starflow.domain.errors import FieldInvalid
from starflow.services.forecast import ForecastService

USER = UUID(int=1)
HISTORY = UUID(int=2)


class _Work:
    def __init__(self, store: object) -> None:
        self._store = store

    async def __aenter__(self) -> object:
        return self._store

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Rows:
    def __init__(
        self,
        rows: tuple[SimpleNamespace, ...],
        payload: dict[str, object] | None,
    ) -> None:
        self.favorites = self
        self.forecast_history = self
        self._rows = rows
        self._payload = payload

    async def list_for_user(self, _user_id: UUID) -> tuple[SimpleNamespace, ...]:
        return self._rows

    async def payload_for(self, _user_id: UUID, _history_id: UUID) -> dict[str, object] | None:
        return self._payload


def _service(store: _Rows) -> ForecastService:
    return ForecastService(
        lambda: _Work(store),
        object(),
        object(),
        object(),
        object(),
        object(),
        object(),
        fast_model="deepseek-flash",
        pro_model="deepseek-v4-pro",
        zone_name="Europe/Moscow",
        locale="ru",
        mini_app_url="https://example.test",
    )


async def test_open_favorite_returns_the_stored_text() -> None:
    service = _service(
        _Rows(
            (SimpleNamespace(target_id=HISTORY, target_type="forecast"),),
            {"title": "День для ясных решений", "body": "Текст дня."},
        )
    )
    assert await service.open_favorite(USER, HISTORY) == ("День для ясных решений", "Текст дня.")


async def test_open_favorite_refuses_a_reading_that_was_not_saved() -> None:
    service = _service(_Rows((), {"title": "День", "body": "Текст дня."}))
    with pytest.raises(FieldInvalid) as caught:
        await service.open_favorite(USER, HISTORY)
    assert caught.value.message_key == "errors.not_found"
