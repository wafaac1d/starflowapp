"""Ошибки домена. Транспорт переводит их в код ответа."""


class DomainError(Exception):
    """Базовая ошибка предметной области."""


class Conflict(DomainError):
    """Уникальный ключ отклонил запись."""


class QuotaExceeded(DomainError):
    """Счётчик упёрся в лимит периода."""


class AuthFailure(DomainError):
    """Подпись Telegram или срок initData не прошли проверку."""


class BirthTimeInvalid(DomainError):
    """Неизвестное время рождения нельзя сохранить вместе с часами."""


class FieldInvalid(DomainError):
    """Поле черновика не прошло проверку. message_key — ключ ресурса."""

    def __init__(self, field: str, message_key: str) -> None:
        super().__init__(message_key)
        self.field = field
        self.message_key = message_key


class PremiumRequired(DomainError):
    """Место рождения в этом срезе сохраняется только на активном периоде."""


class PaymentUnavailable(DomainError):
    """Telegram не подтвердил вызов. Доступ от этого вызова не меняется."""
