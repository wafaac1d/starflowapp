"""Ответ модели — данные для экрана, не разметка и не инструкция к исполнению."""

import re

from starflow.i18n.guard import contains_emoji

_TAG = re.compile(r"<[^>]*>")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARK = re.compile(r"[*_`#>]+")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_ENTITIES = ("&amp;", "&lt;", "&gt;")


def plain_text(value: str) -> str:
    without_fences = _FENCE.sub(" ", value)
    without_links = _LINK.sub(r"\1", without_fences)
    without_tags = _TAG.sub("", without_links)
    without_marks = _MARK.sub("", without_tags)
    collapsed = " ".join(without_marks.split())
    return collapsed.lower()


def guarded_copy(title: str, body: str) -> tuple[str, str] | None:
    clean_title = plain_text(title)
    clean_body = plain_text(body)
    if clean_title == "" or clean_body == "":
        return None
    if contains_emoji(clean_title) or contains_emoji(clean_body):
        return None
    if any(character.isupper() for character in f"{clean_title}{clean_body}"):
        return None
    return clean_title, clean_body


def telegram_chunks(text: str, limit: int = 4096) -> list[str]:
    """Экранирует HTML и режет уже безопасный текст, не разрывая сущность."""
    if limit < 8:
        raise ValueError("telegram chunk limit is too small")
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    chunks: list[str] = []
    rest = escaped
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 0, limit + 1)
        if cut < limit // 2:
            cut = _safe_cut(rest, limit)
        piece = rest[:cut].rstrip("\n")
        if piece == "":
            piece = rest[:limit]
            cut = limit
        chunks.append(piece)
        rest = rest[cut:].lstrip("\n")
    return chunks


def _safe_cut(value: str, limit: int) -> int:
    cut = limit
    window = value[max(0, cut - 5) : cut]
    amp = window.rfind("&")
    if amp == -1:
        return cut
    tail = window[amp:]
    if any(entity.startswith(tail) and tail != entity for entity in _ENTITIES):
        return max(1, cut - (len(window) - amp))
    return cut
