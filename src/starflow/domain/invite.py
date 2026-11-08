"""Ссылка приглашения открывает бота в Telegram, а не страницу сайта."""

import re
from urllib.parse import parse_qsl, urlsplit

from starflow.domain.start_param import normalize_start_param

_BOT_NAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def clean_bot_username(value: str | None) -> str:
    if value is None:
        return ""
    name = value.strip().lstrip("@")
    if _BOT_NAME.fullmatch(name) is None:
        return ""
    return name


def referral_link(web_url: str, code: str, bot_username: str) -> str:
    payload = f"ref_{code}"
    name = clean_bot_username(bot_username)
    if name:
        return f"https://t.me/{name}?start={payload}"
    parts = urlsplit(web_url.strip())
    host = parts.netloc.lower()
    if host == "t.me" or host.endswith(".t.me"):
        join = "&" if "?" in web_url else "?"
        return f"{web_url}{join}startapp={payload}"
    return ""


def referral_payload(query: str) -> str | None:
    found = ""
    for key, value in parse_qsl(query, keep_blank_values=False):
        if key in {"startapp", "start", "tgWebAppStartParam"} and value.startswith("ref_"):
            found = value
            break
    normalized = normalize_start_param(found)
    if normalized is None or not normalized.startswith("ref_"):
        return None
    return normalized


def referral_redirect_url(query: str, bot_username: str) -> str | None:
    payload = referral_payload(query)
    name = clean_bot_username(bot_username)
    if payload is None or name == "":
        return None
    return f"https://t.me/{name}?start={payload}"
