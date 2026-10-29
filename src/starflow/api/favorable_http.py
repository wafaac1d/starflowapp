"""Благоприятные дни месяца для выбранного события."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from starflow.api.actor import actor_from_cookie
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid
from starflow.services.favorable import FavorableMonth


class FavorableDayBody(BaseModel):
    date: str
    start: str
    end: str
    note: str


class FavorableMonthBody(BaseModel):
    status: str
    event: str
    label: str
    month: str
    timezone: str
    days: list[FavorableDayBody]


def register_favorable_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")

    @router.get("/favorable", response_model=FavorableMonthBody)
    async def read_favorable(
        request: Request,
        month: Annotated[str, Query()],
        event: Annotated[str, Query()],
        custom: Annotated[str, Query()] = "",
    ) -> FavorableMonthBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await container.favorable_service.month(actor.view.user_id, month, event, custom)
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return _body(view)


def _body(view: FavorableMonth) -> FavorableMonthBody:
    return FavorableMonthBody(
        status=view.status,
        event=view.event,
        label=view.label,
        month=view.month,
        timezone=view.timezone,
        days=[
            FavorableDayBody(date=day.date, start=day.start, end=day.end, note=day.note)
            for day in view.days
        ],
    )


def _field_error(container: Container, error: FieldInvalid) -> ApiError:
    message = container.catalog.text(error.message_key)
    return ApiError(422, "validation", message, {error.field: message})
