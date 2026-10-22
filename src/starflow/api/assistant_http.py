"""Диалог помощника. Транспорт только вызывает сценарий."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid


class QuestionBody(BaseModel):
    text: str


class AssistantBody(BaseModel):
    status: str
    reply: str | None = None
    remaining: int | None = None
    replayed: bool = False
    code: str | None = None


class AssistantMessageBody(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


def register_assistant_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")

    @router.post("/assistant/messages", response_model=AssistantBody)
    async def ask_assistant(
        body: QuestionBody,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> AssistantBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            reply = await container.assistant_service.ask(
                actor.view.user_id, idempotency_key, body.text
            )
        except FieldInvalid as error:
            raise ApiError(
                422,
                "validation",
                container.catalog.text(error.message_key),
                {error.field: container.catalog.text(error.message_key)},
            ) from error
        return AssistantBody(
            status=reply.status,
            reply=reply.reply,
            remaining=reply.remaining,
            replayed=reply.replayed,
            code=reply.code,
        )

    @router.get("/assistant/messages", response_model=list[AssistantMessageBody])
    async def list_assistant(
        request: Request,
        limit: Annotated[int, Query()] = 30,
        before: Annotated[datetime | None, Query()] = None,
    ) -> list[AssistantMessageBody]:
        actor = await actor_from_cookie(request, container, unauthorized)
        rows = await container.assistant_service.history(
            actor.view.user_id, limit=limit, before=before
        )
        return [
            AssistantMessageBody(
                id=item.id, role=item.role, content=item.content, created_at=item.created_at
            )
            for item in rows
        ]
