from datetime import date, time
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from starflow.api.actor import Actor, actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid, PremiumRequired
from starflow.domain.records import PlaceHit, Profile
from starflow.services.profile import DraftInput


class ProfileBody(BaseModel):
    user_id: UUID
    is_admin: bool
    is_premium: bool
    step: str
    display_name: str | None
    birth_date: str | None
    birth_time: str | None
    birth_time_unknown: bool
    timezone: str | None
    birth_place: str | None
    latitude: str | None
    longitude: str | None
    calendar_sign: str | None


class DraftBody(BaseModel):
    display_name: str | None = None
    birth_date: str | None = None
    birth_time: str | None = None
    birth_time_unknown: bool = False
    timezone: str | None = None


class PlaceSearchBody(BaseModel):
    query: str


class PlaceHitBody(BaseModel):
    label: str
    latitude: str
    longitude: str


class PlaceBody(BaseModel):
    query: str
    label: str
    latitude: str
    longitude: str


def register_profile_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")
    not_found = container.catalog.text("errors.not_found")

    @router.post("/profile/draft", response_model=ProfileBody)
    async def save_draft(request: Request, body: DraftBody) -> ProfileBody:
        actor = await _actor(request, container, unauthorized)
        try:
            await container.profile_service.continue_draft(actor.view.user_id, _draft(body))
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return await profile_body(container, actor.view.user_id, actor.view.is_admin)

    @router.post("/profile/back", response_model=ProfileBody)
    async def step_back(request: Request) -> ProfileBody:
        actor = await _actor(request, container, unauthorized)
        await container.profile_service.go_back(actor.view.user_id)
        return await profile_body(container, actor.view.user_id, actor.view.is_admin)

    @router.patch("/profile", response_model=ProfileBody)
    async def edit_profile(request: Request, body: DraftBody) -> ProfileBody:
        actor = await _actor(request, container, unauthorized)
        try:
            await container.profile_service.edit(actor.view.user_id, _draft(body))
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return await profile_body(container, actor.view.user_id, actor.view.is_admin)

    @router.post("/places/search", response_model=list[PlaceHitBody])
    async def search_places(request: Request, body: PlaceSearchBody) -> list[PlaceHitBody]:
        actor = await _actor(request, container, unauthorized)
        try:
            hits = await container.place_service.search(actor.view.user_id, body.query)
        except PremiumRequired as error:
            raise _premium(container) from error
        return [_hit(item) for item in hits]

    @router.post("/profile/place", response_model=ProfileBody)
    async def confirm_place(request: Request, body: PlaceBody) -> ProfileBody:
        actor = await _actor(request, container, unauthorized)
        try:
            await container.profile_service.confirm_place(
                actor.view.user_id, body.query, body.label, body.latitude, body.longitude
            )
        except PremiumRequired as error:
            raise _premium(container) from error
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return await profile_body(container, actor.view.user_id, actor.view.is_admin)

    @router.delete("/profile")
    async def delete_profile(request: Request) -> dict[str, bool]:
        actor = await _actor(request, container, unauthorized)
        await container.session_service.delete_account(actor.view.user_id)
        return {"deleted": True}

    @router.get("/history/{history_id}")
    async def own_history(history_id: UUID, request: Request) -> dict[str, str]:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not await container.access_service.owns_history(actor.view.user_id, history_id):
            raise ApiError(404, "not_found", not_found)
        return {"history_id": str(history_id)}

    @router.get("/assistant/messages/{message_id}")
    async def own_message(message_id: UUID, request: Request) -> dict[str, str]:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not await container.access_service.owns_message(actor.view.user_id, message_id):
            raise ApiError(404, "not_found", not_found)
        return {"message_id": str(message_id)}

    @router.get("/orders/{order_id}")
    async def own_order(order_id: UUID, request: Request) -> dict[str, str]:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not await container.access_service.owns_order(actor.view.user_id, order_id):
            raise ApiError(404, "not_found", not_found)
        return {"order_id": str(order_id)}

    @router.get("/admin/status")
    async def admin_status(request: Request) -> dict[str, bool]:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(404, "not_found", not_found)
        return {"is_admin": True}


async def profile_body(container: Container, user_id: UUID, is_admin: bool) -> ProfileBody:
    profile, premium, sign = await container.profile_service.read(user_id)
    return _body(user_id, is_admin, premium, sign, profile)


async def _actor(request: Request, container: Container, unauthorized: str) -> Actor:
    require_intent(request, unauthorized)
    return await actor_from_cookie(request, container, unauthorized)


def _draft(body: DraftBody) -> DraftInput:
    return DraftInput(
        display_name=body.display_name,
        birth_date=body.birth_date,
        birth_time=body.birth_time,
        birth_time_unknown=body.birth_time_unknown,
        timezone=body.timezone,
    )


def _field_error(container: Container, error: FieldInvalid) -> ApiError:
    message = container.catalog.text(error.message_key)
    return ApiError(
        422,
        "validation_error",
        container.catalog.text("errors.validation"),
        {error.field: message},
    )


def _premium(container: Container) -> ApiError:
    return ApiError(403, "premium_required", container.catalog.text("errors.premium_required"))


def _hit(item: PlaceHit) -> PlaceHitBody:
    return PlaceHitBody(
        label=item.label,
        latitude=str(item.latitude),
        longitude=str(item.longitude),
    )


def _body(
    user_id: UUID,
    is_admin: bool,
    premium: bool,
    sign: str | None,
    profile: Profile,
) -> ProfileBody:
    return ProfileBody(
        user_id=user_id,
        is_admin=is_admin,
        is_premium=premium,
        step=profile.onboarding_step,
        display_name=profile.display_name,
        birth_date=_date(profile.birth_date),
        birth_time=_clock(profile.birth_time),
        birth_time_unknown=profile.birth_time_unknown,
        timezone=profile.timezone,
        birth_place=profile.birth_place,
        latitude=None if profile.latitude is None else str(profile.latitude),
        longitude=None if profile.longitude is None else str(profile.longitude),
        calendar_sign=sign,
    )


def _date(value: date | None) -> str | None:
    if value is None:
        return None
    return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"


def _clock(value: time | None) -> str | None:
    if value is None:
        return None
    return f"{value.hour:02d}:{value.minute:02d}"
