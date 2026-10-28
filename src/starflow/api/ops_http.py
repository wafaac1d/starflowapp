"""Настройки уведомлений, ретроградные периоды и сводка администратора."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid
from starflow.domain.time import now_utc


class NoticeBody(BaseModel):
    local_time: str
    timezone: str
    day: bool
    moon: bool
    retro: bool


class NoticeWrite(BaseModel):
    local_time: str = Field(min_length=5, max_length=5)
    timezone: str = Field(min_length=1, max_length=64)
    day: bool
    moon: bool
    retro: bool


class RetroPeriodBody(BaseModel):
    planet: str
    start: str
    end: str


class SourceCount(BaseModel):
    source: str
    count: int


class ModelCount(BaseModel):
    model: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    errors: int
    latency_p50_ms: int | None


class FeedbackCountBody(BaseModel):
    forecast_type: str
    prompt_version: str
    count: int


class CacheCount(BaseModel):
    l1_hits: int
    l1_misses: int
    l2_hits: int
    process_generations: int
    rows_in_range: int
    hits_in_range: int


class AdminUserBody(BaseModel):
    user_id: UUID
    telegram_id: int
    username: str | None
    display_name: str | None
    premium: bool


class AdminUsersBody(BaseModel):
    users: list[AdminUserBody]
    total: int
    page: int
    page_size: int


class BalanceCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    stars: int = Field(ge=1, le=10000)
    uses: int = Field(ge=1, le=10000)
    days: int = Field(ge=1, le=366)


class BalanceCodeCreated(BaseModel):
    code: str


class BroadcastCreate(BaseModel):
    body: str = Field(min_length=1, max_length=500)
    audience: str = Field(min_length=1, max_length=16)


class BroadcastCreated(BaseModel):
    id: UUID
    status: str


class AdminBody(BaseModel):
    start: date
    end: date
    active_users: int
    open_accounts: int
    payments: int
    stars: int
    refunds: int
    sources: list[SourceCount]
    models: list[ModelCount]
    cache: CacheCount
    feedback: list[FeedbackCountBody]
    definitions: dict[str, str]


def register_ops_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")
    ops = container.ops_service

    @router.get("/notifications", response_model=NoticeBody)
    async def read_notifications(request: Request) -> NoticeBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        local_time, zone, day, moon, retro = await ops.preferences(actor.view.user_id)
        return NoticeBody(
            local_time=local_time,
            timezone=zone,
            day=day,
            moon=moon,
            retro=retro,
        )

    @router.put("/notifications", response_model=NoticeBody)
    async def write_notifications(body: NoticeWrite, request: Request) -> NoticeBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            saved = await ops.save_preferences(
                actor.view.user_id,
                body.local_time,
                body.timezone,
                day=body.day,
                moon=body.moon,
                retro=body.retro,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error
        return NoticeBody(
            local_time=saved[0],
            timezone=saved[1],
            day=saved[2],
            moon=saved[3],
            retro=saved[4],
        )

    @router.get("/retro", response_model=list[RetroPeriodBody])
    async def read_retro(request: Request) -> list[RetroPeriodBody]:
        await actor_from_cookie(request, container, unauthorized)
        found = await ops.retrograde_periods()
        return [
            RetroPeriodBody(planet=planet, start=start, end=end) for planet, start, end in found
        ]

    @router.get("/admin/overview", response_model=AdminBody)
    async def admin_overview(
        request: Request,
        start: Annotated[date | None, Query()] = None,
        end: Annotated[date | None, Query()] = None,
    ) -> AdminBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(403, "unauthorized", unauthorized)
        try:
            window = _window(start, end)
        except FieldInvalid as error:
            raise _field(container, error) from error
        snap = await ops.snapshot(window[0], window[1])
        cache = container.forecast_cache
        catalog = container.catalog
        return AdminBody(
            start=window[0].date(),
            end=(window[1] - timedelta(days=1)).date(),
            active_users=snap.active_users,
            open_accounts=snap.open_accounts,
            payments=snap.payments,
            stars=snap.stars,
            refunds=snap.refunds,
            sources=[SourceCount(source=name, count=count) for name, count in snap.sources],
            models=[
                ModelCount(
                    model=item.model,
                    calls=item.calls,
                    prompt_tokens=item.prompt_tokens,
                    completion_tokens=item.completion_tokens,
                    errors=item.errors,
                    latency_p50_ms=item.latency_p50_ms,
                )
                for item in snap.models
            ],
            cache=CacheCount(
                l1_hits=cache.l1_hits,
                l1_misses=cache.l1_misses,
                l2_hits=cache.l2_hits,
                process_generations=cache.generations,
                rows_in_range=snap.cache_rows,
                hits_in_range=snap.cache_hits,
            ),
            feedback=[
                FeedbackCountBody(
                    forecast_type=item.forecast_type,
                    prompt_version=item.prompt_version,
                    count=item.count,
                )
                for item in snap.feedback
            ],
            definitions={
                "active_users": catalog.text("ui.admin.active_users"),
                "open_accounts": catalog.text("ui.admin.open_accounts"),
                "payments": catalog.text("ui.admin.payments"),
                "cache": catalog.text("ui.admin.cache"),
                "feedback": catalog.text("ui.admin.feedback"),
                "range": catalog.text("ui.admin.range"),
            },
        )

    @router.get("/admin/users", response_model=AdminUsersBody)
    async def admin_users(
        request: Request,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=50)] = 10,
    ) -> AdminUsersBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(403, "unauthorized", unauthorized)
        rows, total = await ops.accounts(page, page_size)
        return AdminUsersBody(
            users=[
                AdminUserBody(
                    user_id=row.user_id,
                    telegram_id=row.telegram_id,
                    username=row.username,
                    display_name=row.display_name,
                    premium=premium,
                )
                for row, premium in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    @router.post("/admin/balance-codes", response_model=BalanceCodeCreated)
    async def create_balance_code(body: BalanceCodeCreate, request: Request) -> BalanceCodeCreated:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(403, "unauthorized", unauthorized)
        try:
            code = await container.stars_service.create_code(
                actor_is_admin=True,
                name=body.code,
                stars=body.stars,
                uses=body.uses,
                days=body.days,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error
        return BalanceCodeCreated(code=code)

    @router.post("/admin/broadcasts", response_model=BroadcastCreated)
    async def create_broadcast(body: BroadcastCreate, request: Request) -> BroadcastCreated:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(403, "unauthorized", unauthorized)
        try:
            broadcast_id = await ops.queue_broadcast(
                actor_is_admin=True,
                body=body.body,
                audience=body.audience,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error
        return BroadcastCreated(id=broadcast_id, status="queued")


def _window(start: date | None, end: date | None) -> tuple[datetime, datetime]:
    today = now_utc().date()
    finish = end or today
    begin = start or (finish - timedelta(days=30))
    if finish < begin or (finish - begin).days > 366:
        raise FieldInvalid("range", "errors.validation")
    return (
        datetime.combine(begin, time.min, tzinfo=UTC),
        datetime.combine(finish + timedelta(days=1), time.min, tzinfo=UTC),
    )


def _field(container: Container, error: FieldInvalid) -> ApiError:
    return ApiError(
        422,
        "validation_error",
        container.catalog.text(error.message_key),
        {error.field: error.message_key},
    )
