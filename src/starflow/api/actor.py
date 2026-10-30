from dataclasses import dataclass

import structlog
from fastapi import Request
from starlette.responses import Response

from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.config import Settings
from starflow.services.session import SessionView

INTENT = "x-starflow-request"


@dataclass(frozen=True)
class Actor:
    view: SessionView


def attach_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_sec,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        path="/",
    )


def require_intent(request: Request, message: str) -> None:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get(INTENT) != "1":
        raise ApiError(403, "unauthorized", message)


async def actor_from_cookie(request: Request, container: Container, message: str) -> Actor:
    token = request.cookies.get(container.settings.session_cookie_name, "")
    view = await container.session_service.resume(token)
    if view is None:
        raise ApiError(401, "unauthorized", message)
    structlog.contextvars.bind_contextvars(
        telegram_id=view.telegram_id,
        telegramId=view.telegram_id,
        user_id=str(view.user_id),
    )
    return Actor(view)
