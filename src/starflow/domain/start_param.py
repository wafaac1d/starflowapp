import re

_START = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def normalize_start_param(value: str | None) -> str | None:
    """Принимает параметр ссылки как есть по регистру и не превращает его в право."""
    if value is None:
        return None
    cleaned = value.strip()
    if _START.fullmatch(cleaned) is None:
        return None
    return cleaned
