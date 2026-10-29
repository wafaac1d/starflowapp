"""Обращения в службу поддержки и администрирование обращений."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid


class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=100)
    message: str = Field(min_length=5, max_length=2000)


class SupportTicketBody(BaseModel):
    id: UUID
    subject: str
    message: str
    status: str
    created_at: datetime


class AdminSupportTicketBody(BaseModel):
    id: UUID
    user_id: UUID
    telegram_id: int
    username: str | None
    display_name: str | None
    subject: str
    message: str
    status: str
    created_at: datetime
    closed_at: datetime | None


class SupportTicketClosedBody(BaseModel):
    id: UUID
    status: str


def register_support_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")

    @router.post("/support", response_model=SupportTicketBody)
    async def create_support_ticket(
        body: SupportTicketCreate, request: Request
    ) -> SupportTicketBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            ticket = await container.support_service.create_ticket(
                actor.view.user_id,
                body.subject,
                body.message,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error
        return SupportTicketBody(
            id=ticket.id,
            subject=ticket.subject,
            message=ticket.message,
            status=ticket.status,
            created_at=ticket.created_at,
        )

    @router.get("/admin/support", response_model=list[AdminSupportTicketBody])
    async def admin_list_support(request: Request) -> list[AdminSupportTicketBody]:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(403, "unauthorized", unauthorized)
        tickets = await container.support_service.admin_list_tickets(actor.view.is_admin)
        return [
            AdminSupportTicketBody(
                id=t.id,
                user_id=t.user_id,
                telegram_id=t.telegram_id,
                username=t.username,
                display_name=t.display_name,
                subject=t.subject,
                message=t.message,
                status=t.status,
                created_at=t.created_at,
                closed_at=t.closed_at,
            )
            for t in tickets
        ]

    @router.post("/admin/support/{ticket_id}/close", response_model=SupportTicketClosedBody)
    async def admin_close_support(ticket_id: UUID, request: Request) -> SupportTicketClosedBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        if not actor.view.is_admin:
            raise ApiError(403, "unauthorized", unauthorized)
        closed = await container.support_service.admin_close_ticket(actor.view.is_admin, ticket_id)
        if not closed:
            raise ApiError(404, "not_found", container.catalog.text("errors.not_found"))
        return SupportTicketClosedBody(id=ticket_id, status="closed")


def _field(container: Container, error: FieldInvalid) -> ApiError:
    message = container.catalog.text(error.message_key)
    return ApiError(422, "validation", message, {error.field: message})
