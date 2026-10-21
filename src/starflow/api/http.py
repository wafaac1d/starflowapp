import hmac
from datetime import datetime
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from starflow.api.spa import SpaKind, resolve_spa
from starflow.domain.errors import AuthFailure
from starflow.services.session import SessionView


class ErrorBody(BaseModel):
    code: str
    message: str


class MetaResponse(BaseModel):
    service: str
    locale: str
    premium_price_stars: int
    premium_period_days: int
    assistant_questions: int
    mini_app_configured: bool


class SessionResponse(BaseModel):
    user_id: UUID
    telegram_id: int
    username: str | None
    is_admin: bool


class ErrorResponse(BaseModel):
    error: ErrorBody
    fields: dict[str, str] | None = None
    reset_at: datetime | None = None


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        reset_at: datetime | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields
        self.reset_at = reset_at


def error_response(
    status: int,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
    reset_at: datetime | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(code=code, message=message),
        fields=fields,
        reset_at=reset_at,
    )
    content = payload.model_dump(mode="json")
    if reset_at is None:
        content.pop("reset_at", None)
    return JSONResponse(status_code=status, content=content)


def session_response(view: SessionView) -> SessionResponse:
    structlog.contextvars.bind_contextvars(user_id=view.telegram_id)
    return SessionResponse(
        user_id=view.user_id,
        telegram_id=view.telegram_id,
        username=view.username,
        is_admin=view.is_admin,
    )


def translate_auth(error: AuthFailure, message: str) -> ApiError:
    structlog.get_logger("auth").info("init_data_rejected", error_type=type(error).__name__)
    return ApiError(401, "unauthorized", message)


def secrets_match(received: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(received, expected)


def register_error_handlers(app: FastAPI, not_found_message: str, validation_message: str) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.fields, exc.reset_at)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "validation_error", validation_message)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404 and request.url.path.startswith("/api"):
            return error_response(404, "not_found", not_found_message)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def add_cors(app: FastAPI, origins: tuple[str, ...]) -> None:
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Starflow-Request",
        ],
    )


_MEDIA = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
}


def spa_response(dist: Path, logo: Path, url_path: str, not_found_message: str) -> Response:
    decision = resolve_spa(dist, logo, url_path)
    if decision.kind is SpaKind.MISSING_API:
        return error_response(404, "not_found", not_found_message)
    if decision.kind in {SpaKind.MISSING_ASSET, SpaKind.MISSING_CLIENT} or decision.file is None:
        return Response(status_code=404, media_type="text/plain")
    media = _MEDIA.get(decision.file.suffix, "application/octet-stream")
    cache = "no-cache" if decision.kind is SpaKind.HTML else "public, max-age=31536000"
    return FileResponse(decision.file, media_type=media, headers={"Cache-Control": cache})
