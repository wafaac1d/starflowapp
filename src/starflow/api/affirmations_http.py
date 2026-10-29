"""Аффирмации на день: один бесплатный расчёт в день и платные категории."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from starflow.api.actor import actor_from_cookie
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
        category: Annotated[str, Query()] = "for_you",
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
