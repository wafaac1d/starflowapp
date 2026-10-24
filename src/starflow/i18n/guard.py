import re

_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
    (0xFE0F, 0xFE0F),
)
_BEARER = re.compile(r"(?:Bearer|TMA)\s+\S+", re.IGNORECASE)
_URL_PASSWORD = re.compile(r"://([^:/]+):([^@]+)@")
_SENSITIVE_PARTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "authorization",
    "init_data",
    "initdata",
    "birth_date",
    "birth_time",
    "birth_place",
    "latitude",
    "longitude",
    "display_name",
    "content",
    "comment",
    "database_url",
    "cookie",
    "start_param",
)


def assert_authored(text: str) -> None:
    if contains_emoji(text):
        raise ValueError("authored text must not contain emoji")


def contains_emoji(text: str) -> bool:
    return any(
        any(start <= ord(character) <= end for start, end in _EMOJI_RANGES) for character in text
    )


def sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_PARTS)


def scrub_text(value: str) -> str:
    without_bearer = _BEARER.sub("Bearer [redacted]", value)
    return _URL_PASSWORD.sub(r"://\1:[redacted]@", without_bearer)


def redact(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[object, object] = {}
        for key, item in value.items():
            if isinstance(key, str) and sensitive_key(key):
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value
