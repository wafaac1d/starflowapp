import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl

from starflow.domain.errors import AuthFailure
from starflow.domain.onboarding import age_allows
from starflow.domain.start_param import normalize_start_param
from starflow.domain.time import now_utc


@dataclass(frozen=True)
class TelegramIdentity:
    telegram_id: int
    username: str | None
    language_code: str | None
    start_param: str | None


class TelegramInitDataVerifier:
    def __init__(self, bot_token: str, max_age_sec: int, future_skew_sec: int = 60) -> None:
        self._bot_token = bot_token
        self._max_age_sec = max_age_sec
        self._future_skew_sec = future_skew_sec

    def verify(self, init_data: str, *, now: datetime | None = None) -> TelegramIdentity:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        values = dict(pairs)
        received = values.pop("hash", "")
        if not received:
            raise AuthFailure("initData has no hash")
        check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        secret = hmac.new(b"WebAppData", self._bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise AuthFailure("initData signature mismatch")
        current = now if now is not None else now_utc()
        auth_date = _unix(values.get("auth_date"))
        if auth_date is None:
            raise AuthFailure("initData has no auth_date")
        if not age_allows(auth_date, current, self._max_age_sec, self._future_skew_sec):
            raise AuthFailure("initData auth_date is outside the allowed window")
        identity = _identity(values.get("user"))
        return TelegramIdentity(
            telegram_id=identity.telegram_id,
            username=identity.username,
            language_code=identity.language_code,
            start_param=normalize_start_param(values.get("start_param")),
        )


def sign_payload(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{digest}"


def read_signed_payload(signed: str, secret: str) -> str:
    payload, separator, digest = signed.rpartition(".")
    if not separator or not payload:
        raise AuthFailure("signed payload is incomplete")
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, digest):
        raise AuthFailure("signed payload mismatch")
    return payload


def _unix(value: str | None) -> float | None:
    if value is None or not value.isdigit():
        return None
    return float(value)


def _identity(raw_user: str | None) -> TelegramIdentity:
    if raw_user is None:
        raise AuthFailure("initData has no user")
    loaded = json.loads(raw_user)
    if not isinstance(loaded, dict):
        raise AuthFailure("initData user is not an object")
    telegram_id = loaded.get("id")
    username = loaded.get("username")
    language_code = loaded.get("language_code")
    if not isinstance(telegram_id, int):
        raise AuthFailure("initData user has no numeric id")
    if username is not None and not isinstance(username, str):
        raise AuthFailure("initData username has the wrong type")
    if language_code is not None and not isinstance(language_code, str):
        raise AuthFailure("initData language_code has the wrong type")
    return TelegramIdentity(
        telegram_id=telegram_id,
        username=username,
        language_code=language_code,
        start_param=None,
    )
