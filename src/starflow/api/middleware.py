from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_id = _header(scope, b"x-request-id") or uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


def _header(scope: Scope, name: bytes) -> str:
    raw_headers = scope.get("headers")
    if not isinstance(raw_headers, list):
        return ""
    for item in raw_headers:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        key, value = item
        if isinstance(key, bytes) and isinstance(value, bytes) and key.lower() == name:
            return value.decode()
    return ""
