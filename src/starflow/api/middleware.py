import json
import time
from urllib.parse import parse_qsl, unquote
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from starflow.i18n.guard import redact

_LOG = structlog.get_logger("http")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        start_time = time.monotonic()
        request_id = _header(scope, b"x-request-id") or uuid4().hex
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        request_type = f"{method} {path}"

        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")
        query_params = dict(parse_qsl(query_string)) if query_string else {}

        auth_header = _header(scope, b"authorization")
        initial_telegram_id = _telegram_id_from_auth(auth_header) if auth_header else None

        bound: dict[str, object] = {
            "request_id": request_id,
            "request_type": request_type,
        }
        if initial_telegram_id is not None:
            bound["telegram_id"] = initial_telegram_id
            bound["telegramId"] = initial_telegram_id
        structlog.contextvars.bind_contextvars(**bound)

        body_chunks: list[bytes] = []

        async def logging_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    body_chunks.append(chunk)
            return message

        status_code = 200

        async def logging_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self._app(scope, logging_receive, logging_send)
        finally:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            body_params: dict[str, object] = {}
            if body_chunks:
                try:
                    parsed = json.loads(b"".join(body_chunks))
                    if isinstance(parsed, dict):
                        body_params = parsed
                    elif isinstance(parsed, list):
                        body_params = {"items": parsed}
                except Exception:
                    pass

            params = {**query_params, **body_params}
            context = structlog.contextvars.get_contextvars()
            telegram_id = context.get("telegramId") or context.get("telegram_id") or initial_telegram_id

            if path not in {"/liveness", "/health", "/readiness"}:
                _LOG.info(
                    "http_request",
                    telegramId=telegram_id,
                    telegram_id=telegram_id,
                    request_type=request_type,
                    method=method,
                    path=path,
                    params=redact(params),
                    status_code=status_code,
                    duration_ms=duration_ms,
                )

            structlog.contextvars.unbind_contextvars(
                "request_id", "request_type", "telegram_id", "telegramId", "user_id"
            )


def _telegram_id_from_auth(auth_header: str) -> int | None:
    if not auth_header.startswith("TMA "):
        return None
    raw = auth_header[4:]
    for part in raw.split("&"):
        if part.startswith("user="):
            try:
                user_json = json.loads(unquote(part[5:]))
                if isinstance(user_json, dict) and "id" in user_json:
                    return int(user_json["id"])
            except Exception:
                pass
    return None


def _header(scope: Scope, name: bytes) -> str:
    raw_headers = scope.get("headers")
    if not isinstance(raw_headers, list):
        return ""
    for item in raw_headers:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        key, value = item
        if isinstance(key, bytes) and isinstance(value, bytes) and key.lower() == name:
            return value.decode("latin1")
    return ""
