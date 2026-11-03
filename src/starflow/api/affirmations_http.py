"""Аффирмации на день: один бесплатный расчёт в день и платные категории."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid
from starflow.services.affirmations import AffirmationsView


class AffirmationCardBody(BaseModel):
    id: str
    text: str
    category: str
    bg_image: str


class AffirmationsBody(BaseModel):
    category: str
    label: str
    access: str
    price: int
    cards: list[AffirmationCardBody]
    free_chosen_label: str | None = None


class AffirmationsStatusBody(BaseModel):
    chosen_category: str | None = None
    chosen_label: str | None = None
    is_premium: bool = False


class AffirmationKeepBody(BaseModel):
    id: UUID
    card_id: str
    text: str
    category: str


class AffirmationKeepWrite(BaseModel):
    card_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=32)


def register_affirmations_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")

    @router.get("/affirmations/status", response_model=AffirmationsStatusBody)
    async def read_affirmations_status(request: Request) -> AffirmationsStatusBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        status = await container.affirmations_service.status(actor.view.user_id)
        return AffirmationsStatusBody(
            chosen_category=status.chosen_category,
            chosen_label=status.chosen_label,
            is_premium=status.is_premium,
        )

    @router.get("/affirmations", response_model=AffirmationsBody)
    async def read_affirmations(
        request: Request,
        category: Annotated[str, Query(min_length=1, max_length=32)],
    ) -> AffirmationsBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await container.affirmations_service.get_affirmations(
                actor.view.user_id,
                category,
            )
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return _body(view)

    @router.get("/affirmations/keeps", response_model=list[AffirmationKeepBody])
    async def read_affirmation_keeps(request: Request) -> list[AffirmationKeepBody]:
        actor = await actor_from_cookie(request, container, unauthorized)
        rows = await container.affirmations_service.list_keeps(actor.view.user_id)
        return [
            AffirmationKeepBody(
                id=row.id, card_id=row.card_id, text=row.text, category=row.category
            )
            for row in rows
        ]

    @router.post("/affirmations/keeps", response_model=AffirmationKeepBody)
    async def create_affirmation_keep(
        body: AffirmationKeepWrite,
        request: Request,
    ) -> AffirmationKeepBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            saved = await container.affirmations_service.keep(
                actor.view.user_id,
                body.card_id,
                body.category,
                body.text,
            )
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return AffirmationKeepBody(
            id=saved.id,
            card_id=saved.card_id,
            text=saved.text,
            category=saved.category,
        )

    @router.delete("/affirmations/keeps/{card_id}", status_code=204)
    async def delete_affirmation_keep(card_id: str, request: Request) -> None:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        await container.affirmations_service.forget(actor.view.user_id, card_id)


def _body(view: AffirmationsView) -> AffirmationsBody:
    return AffirmationsBody(
        category=view.category,
        label=view.label,
        access=view.access,
        price=view.price,
        cards=[
            AffirmationCardBody(
                id=card.id,
                text=card.text,
                category=card.category,
                bg_image=card.bg_image,
            )
            for card in view.cards
        ],
        free_chosen_label=view.free_chosen_label,
    )


def _field_error(container: Container, error: FieldInvalid) -> ApiError:
    message = container.catalog.text(error.message_key)
    return ApiError(422, "validation", message, {error.field: message})
