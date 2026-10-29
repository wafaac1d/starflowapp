from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.gzip import GZipMiddleware

from starflow.api.actor import (
    actor_from_cookie,
    attach_session_cookie,
    clear_session_cookie,
    require_intent,
)
from starflow.api.assistant_http import register_assistant_routes
from starflow.api.billing_http import register_billing_routes
from starflow.api.chart_http import register_chart_routes
from starflow.api.favorable_http import register_favorable_routes
from starflow.api.forecast_http import register_forecast_routes
from starflow.api.http import (
    ApiError,
    MetaResponse,
    add_cors,
    error_response,
    register_error_handlers,
    secrets_match,
    spa_response,
    translate_auth,
)
from starflow.api.middleware import RequestIdMiddleware
from starflow.api.ops_http import register_ops_routes
from starflow.api.profile_http import ProfileBody, profile_body, register_profile_routes
from starflow.api.stars_http import register_star_routes
from starflow.bootstrap import Container
from starflow.domain.errors import AuthFailure


def build_fastapi(container: Container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await container.startup()
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(title="StarFlow", version="0.1.0", lifespan=lifespan)
    app.state.container = container
    add_cors(app, container.settings.allowed_origins)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestIdMiddleware)
    catalog = container.catalog
    register_error_handlers(
        app,
        catalog.text("errors.not_found"),
        catalog.text("errors.validation"),
    )
    _register_probes(app, container)
    app.include_router(_api_router(container), prefix="/api/v1")
    _register_webhook(app, container)
    _register_spa(app, container)
    return app


def _register_probes(app: FastAPI, container: Container) -> None:
    @app.get("/liveness")
    async def liveness() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health")
    async def health() -> Response:
        return await _readiness(container)

    @app.get("/readiness")
    async def readiness() -> Response:
        return await _readiness(container)


async def _readiness(container: Container) -> Response:
    if await container.health_service.ready():
        return Response(
            content='{"status":"ready"}',
            media_type="application/json",
            status_code=200,
        )
    return Response(
        content='{"status":"unavailable"}',
        media_type="application/json",
        status_code=503,
    )


def _api_router(container: Container) -> APIRouter:
    router = APIRouter()

    @router.get("/meta", response_model=MetaResponse)
    async def meta() -> MetaResponse:
        plans = container.settings.runtime_plans()
        return MetaResponse(
            service="starflow",
            locale=container.settings.default_locale,
            premium_price_stars=plans.premium.price_stars,
            premium_period_days=plans.premium.period_days,
            assistant_questions=plans.premium.assistant_questions,
            mini_app_configured=bool(container.settings.mini_app_url),
        )

    unauthorized = container.catalog.text("errors.unauthorized")

    @router.post("/session", response_model=ProfileBody)
    async def open_session(request: Request, response: Response) -> ProfileBody:
        require_intent(request, unauthorized)
        header = request.headers.get("authorization", "")
        prefix = "TMA "
        if not header.startswith(prefix):
            raise translate_auth(AuthFailure("missing tma header"), unauthorized)
        try:
            identity = container.verifier.verify(header.removeprefix(prefix).strip())
        except AuthFailure as error:
            raise translate_auth(error, unauthorized) from error
        view = await container.session_service.accept_telegram_user(
            identity.telegram_id,
            identity.username,
            identity.language_code,
            identity.start_param,
        )
        issued = await container.session_service.issue(view)
        attach_session_cookie(response, container.settings, issued.token)
        return await profile_body(container, view.user_id, view.is_admin)

    @router.post("/session/dev", response_model=ProfileBody)
    async def open_dev_session(request: Request, response: Response) -> ProfileBody:
        require_intent(request, unauthorized)
        if not container.settings.allows_dev_auth:
            raise ApiError(404, "not_found", container.catalog.text("errors.not_found"))
        raw = request.headers.get("x-starflow-dev-user", "")
        if not raw.isdigit():
            raise ApiError(401, "unauthorized", unauthorized)
        view = await container.session_service.accept_telegram_user(int(raw), None, None)
        issued = await container.session_service.issue(view)
        attach_session_cookie(response, container.settings, issued.token)
        return await profile_body(container, view.user_id, view.is_admin)

    @router.get("/session", response_model=ProfileBody)
    async def current_session(request: Request) -> ProfileBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        return await profile_body(container, actor.view.user_id, actor.view.is_admin)

    @router.post("/session/logout")
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        require_intent(request, unauthorized)
        token = request.cookies.get(container.settings.session_cookie_name, "")
        await container.session_service.logout(token)
        clear_session_cookie(response, container.settings)
        return {"logged_out": True}

    register_profile_routes(router, container)
    register_chart_routes(router, container)
    register_forecast_routes(router, container)
    register_billing_routes(router, container)
    register_star_routes(router, container)
    register_assistant_routes(router, container)
    register_ops_routes(router, container)
    register_favorable_routes(router, container)
    return router


def _register_webhook(app: FastAPI, container: Container) -> None:
    path = container.settings.webhook_path or "/telegram/webhook"

    @app.post(path)
    async def telegram_webhook(request: Request) -> Response:
        if container.settings.bot_mode != "webhook":
            return error_response(404, "not_found", container.catalog.text("errors.not_found"))
        received = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not secrets_match(received, container.settings.webhook_secret):
            return error_response(
                401,
                "unauthorized",
                container.catalog.text("errors.webhook_rejected"),
            )
        update = Update.model_validate(await request.json(), context={"bot": container.bot})
        structlog_update(update.update_id)
        await container.dispatcher.feed_update(container.bot, update)
        return Response(status_code=200)


def structlog_update(update_id: int) -> None:
    import structlog

    structlog.contextvars.bind_contextvars(update_id=update_id)


def _register_spa(app: FastAPI, container: Container) -> None:
    not_found = container.catalog.text("errors.not_found")

    @app.get("/", include_in_schema=False)
    async def root() -> Response:
        return spa_response(
            container.settings.frontend_dist,
            container.settings.logo_path,
            "/",
            not_found,
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> Response:
        return spa_response(
            container.settings.frontend_dist,
            container.settings.logo_path,
            f"/{full_path}",
            not_found,
        )
