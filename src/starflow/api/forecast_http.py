"""Чтения, история, оценка, близкие и ссылка приглашения."""

from datetime import datetime, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.onboarding import optional_birth_time, parse_birth_date, parse_display_name
from starflow.domain.quota import LimitReached, PremiumRequired
from starflow.domain.records import ProfileDraft
from starflow.domain.time import now_utc
from starflow.services.forecast import ReadingScope, ReadingView
from starflow.services.quota import QuotaStore, StoredResult


class DayBody(BaseModel):
    date: str
    scores: dict[str, int]
    note: str


class ReadingBody(BaseModel):
    status: str
    title: str | None = None
    body: str | None = None
    greeting: str | None = None
    user_sign: str | None = None
    shared_facts: str | None = None
    history_id: UUID | None = None
    streak: int | None = None
    replayed: bool = False
    reset_at: datetime | None = None
    days: list[DayBody] = []
    limitations: list[str] = []


class HistoryItem(BaseModel):
    history_id: UUID
    kind: str
    period_date: str
    title: str


class FavoriteItem(BaseModel):
    history_id: UUID
    title: str


class FeedbackBody(BaseModel):
    score: int


class ShareBody(BaseModel):
    text: str


class ReferralBody(BaseModel):
    code: str
    link: str


class RelatedBody(BaseModel):
    display_name: str
    birth_date: str
    consent: bool = False
    birth_time: str | None = None
    birth_time_unknown: bool = True


class RelatedItem(BaseModel):
    related_id: UUID
    display_name: str
    birth_date: str | None
    birth_time: str | None = None
    birth_time_unknown: bool = True
    consent: bool = False


def register_forecast_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")

    @router.post("/readings/{kind}", response_model=ReadingBody)
    async def start_reading(
        kind: str,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        topic: Annotated[str, Query()] = "",
        month: Annotated[str, Query()] = "",
        related_id: Annotated[UUID | None, Query()] = None,
        left_sign: Annotated[str, Query()] = "",
        right_sign: Annotated[str, Query()] = "",
    ) -> ReadingBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        scope = ReadingScope(
            topic=topic,
            month=month,
            related_id=related_id,
            left_sign=left_sign,
            right_sign=right_sign,
        )
        try:
            view = await container.forecast_service.start(
                actor.view.user_id, kind, idempotency_key, scope
            )
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return _reading(view)

    @router.get("/readings/{kind}", response_model=ReadingBody)
    async def read_reading(
        kind: str,
        request: Request,
        topic: Annotated[str, Query()] = "",
        month: Annotated[str, Query()] = "",
        related_id: Annotated[UUID | None, Query()] = None,
        left_sign: Annotated[str, Query()] = "",
        right_sign: Annotated[str, Query()] = "",
    ) -> ReadingBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        scope = ReadingScope(
            topic=topic,
            month=month,
            related_id=related_id,
            left_sign=left_sign,
            right_sign=right_sign,
        )
        try:
            view = await container.forecast_service.current(actor.view.user_id, kind, scope)
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return _reading(view)

    @router.get("/history", response_model=list[HistoryItem])
    async def read_history(request: Request) -> list[HistoryItem]:
        actor = await actor_from_cookie(request, container, unauthorized)
        rows = await container.forecast_service.history(actor.view.user_id)
        return [
            HistoryItem(
                history_id=item[0], kind=item[1], period_date=item[2].isoformat(), title=item[3]
            )
            for item in rows
        ]

    @router.get("/favorites", response_model=list[FavoriteItem])
    async def read_favorites(request: Request) -> list[FavoriteItem]:
        actor = await actor_from_cookie(request, container, unauthorized)
        rows = await container.forecast_service.favorites(actor.view.user_id)
        return [FavoriteItem(history_id=item[0], title=item[1]) for item in rows]

    @router.post("/readings/{history_id}/feedback", status_code=204)
    async def add_feedback(history_id: UUID, body: FeedbackBody, request: Request) -> None:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            await container.forecast_service.feedback(actor.view.user_id, history_id, body.score)
        except FieldInvalid as error:
            raise _field_error(container, error) from error

    @router.get("/share/{history_id}", response_model=ShareBody)
    async def read_share(history_id: UUID, request: Request) -> ShareBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            text = await container.forecast_service.share(actor.view.user_id, history_id)
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return ShareBody(text=text)

    @router.get("/referral", response_model=ReferralBody)
    async def read_referral(request: Request) -> ReferralBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        code, link = await container.forecast_service.referral(actor.view.user_id)
        return ReferralBody(code=code, link=link)

    @router.get("/related", response_model=list[RelatedItem])
    async def read_related(request: Request) -> list[RelatedItem]:
        actor = await actor_from_cookie(request, container, unauthorized)
        rows = await container.forecast_service.related(actor.view.user_id)
        return [
            RelatedItem(
                related_id=item.id,
                display_name=item.display_name,
                birth_date=None if item.birth_date is None else item.birth_date.isoformat(),
                birth_time=_clock(item.birth_time),
                birth_time_unknown=item.birth_time_unknown,
                consent=item.consent,
            )
            for item in rows
        ]

    @router.post("/related", response_model=RelatedItem)
    async def add_related(
        body: RelatedBody,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> RelatedItem:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            name = parse_display_name(body.display_name)
            born = parse_birth_date(body.birth_date, today=now_utc().date())
            clock, unknown = optional_birth_time(body.birth_time, body.birth_time_unknown)
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        draft = ProfileDraft(
            display_name=name,
            birth_date=born,
            birth_time=clock,
            birth_time_unknown=unknown,
            birth_place=None,
            latitude=None,
            longitude=None,
            timezone=container.settings.default_timezone,
        )
        stored_time = _clock(clock)

        async def producer(store: QuotaStore) -> dict[str, object]:
            related_id = await store.related_profiles.add(
                actor.view.user_id, draft, consent=body.consent
            )
            return {
                "related_id": str(related_id),
                "display_name": name,
                "birth_date": born.isoformat(),
                "birth_time": stored_time,
                "birth_time_unknown": unknown,
                "consent": body.consent,
            }

        try:
            result = await container.quota_service.execute(
                actor.view.user_id,
                "related_profile",
                idempotency_key,
                producer,
            )
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        except Conflict as error:
            raise ApiError(409, "conflict", container.catalog.text("errors.conflict")) from error
        if isinstance(result, LimitReached):
            raise ApiError(429, "limit_reached", container.catalog.text("errors.limit_reached"))
        if isinstance(result, PremiumRequired):
            raise ApiError(
                402, "premium_required", container.catalog.text("errors.premium_required")
            )
        if not isinstance(result, StoredResult):
            raise ApiError(409, "conflict", container.catalog.text("errors.conflict"))
        raw_time = result.body.get("birth_time")
        return RelatedItem(
            related_id=UUID(str(result.body["related_id"])),
            display_name=str(result.body["display_name"]),
            birth_date=str(result.body["birth_date"]),
            birth_time=None if raw_time is None else str(raw_time),
            birth_time_unknown=bool(result.body.get("birth_time_unknown", True)),
            consent=bool(result.body.get("consent")),
        )

    @router.post("/related/{related_id}/consent", status_code=204)
    async def allow_related(related_id: UUID, request: Request) -> None:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        allowed = await container.forecast_service.allow_related(actor.view.user_id, related_id)
        if not allowed:
            raise ApiError(404, "not_found", container.catalog.text("errors.not_found"))

    @router.delete("/related/{related_id}", status_code=204)
    async def remove_related(related_id: UUID, request: Request) -> None:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        deleted = await container.forecast_service.delete_related(actor.view.user_id, related_id)
        if not deleted:
            raise ApiError(404, "not_found", container.catalog.text("errors.not_found"))


def _reading(view: ReadingView) -> ReadingBody:
    return ReadingBody(
        status=view.status,
        title=view.title,
        body=view.body,
        greeting=view.greeting,
        user_sign=view.user_sign,
        shared_facts=view.shared_facts,
        history_id=view.history_id,
        streak=view.streak,
        replayed=view.replayed,
        reset_at=view.reset_at,
        days=[
            DayBody(date=mark.day, scores=dict(mark.scores), note=mark.note) for mark in view.days
        ],
        limitations=list(view.limitations),
    )


def _clock(value: time | None) -> str | None:
    if value is None:
        return None
    return f"{value.hour:02d}:{value.minute:02d}"


def _field_error(container: Container, error: FieldInvalid) -> ApiError:
    message = container.catalog.text(error.message_key)
    status = 404 if error.message_key == "errors.not_found" else 422
    return ApiError(status, "validation", message, {error.field: message})
