"""Редакция соглашения, которую человек принимает при регистрации."""

PRIVACY_VERSION = "2026-11-05"


def privacy_is_current(version: str | None) -> bool:
    return version == PRIVACY_VERSION
