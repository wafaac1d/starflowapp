"""Счета Stars. Роутер только вызывает сценарий."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid, PaymentUnavailable
from starflow.services.billing import BillingView


class BillingBody(BaseModel):
    premium: bool
    access_until: datetime | None
    price_stars: int
    period_days: int
    gift_days: int
    trial_days: int
    assistant_questions: int
    subscription_payment_state: str
    gift_payment_state: str
    subscription_state: str
    auto_renew: bool
    subscription_order_id: UUID | None
    subscription_invoice_link: str | None
    gift_order_id: UUID | None
    gift_invoice_link: str | None
    gift_code: str | None
    gift_link: str | None
    trial_available: bool
    period_end: datetime | None


class OrderBody(BaseModel):
    kind: str


class ClientStatusBody(BaseModel):
    status: str


class RedeemBody(BaseModel):
    code: str = Field(max_length=80)


class CancelBody(BaseModel):
    is_canceled: bool


class RefundBody(BaseModel):
    telegram_payment_charge_id: str = Field(min_length=1, max_length=128)
    confirm: bool
    reason: str = Field(max_length=500)


class AdminGrantBody(BaseModel):
    user_id: UUID
    days: int
    reason: str = Field(max_length=500)


def register_billing_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")
    billing = container.billing_service

    @router.get("/billing", response_model=BillingBody)
    async def read_billing(request: Request) -> BillingBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        view = await billing.view(actor.view.user_id)
        return _body(view)

    @router.post("/billing/orders", response_model=BillingBody)
    async def create_order(
        body: OrderBody,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> BillingBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await billing.create_invoice(actor.view.user_id, body.kind, idempotency_key)
        except FieldInvalid as error:
            raise _field(container, error) from error
        except PaymentUnavailable as error:
            raise _unavailable(container) from error
        return _body(view)

    @router.post("/billing/orders/{order_id}/client-status", response_model=BillingBody)
    async def note_client_status(
        order_id: UUID,
        body: ClientStatusBody,
        request: Request,
    ) -> BillingBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await billing.note_client_status(actor.view.user_id, order_id, body.status)
        except FieldInvalid as error:
            raise _field(container, error) from error
        return _body(view)

    @router.post("/billing/subscription", response_model=BillingBody)
    async def edit_subscription(body: CancelBody, request: Request) -> BillingBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await billing.set_canceled(actor.view.user_id, body.is_canceled)
        except FieldInvalid as error:
            raise _field(container, error) from error
        except PaymentUnavailable as error:
            raise _unavailable(container) from error
        return _body(view)

    @router.post("/billing/trial", response_model=BillingBody)
    async def start_trial(request: Request) -> BillingBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await billing.start_trial(actor.view.user_id)
        except FieldInvalid as error:
            raise _field(container, error) from error
        return _body(view)

    @router.post("/billing/gifts/redeem", response_model=BillingBody)
    async def redeem_gift(body: RedeemBody, request: Request) -> BillingBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await billing.redeem(actor.view.user_id, body.code)
        except FieldInvalid as error:
            raise _field(container, error) from error
        return _body(view)

    @router.post("/billing/refunds", status_code=204)
    async def refund_charge(body: RefundBody, request: Request) -> None:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            await billing.refund(
                actor_is_admin=actor.view.is_admin,
                charge_id=body.telegram_payment_charge_id,
                confirm=body.confirm,
                reason=body.reason,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error
        except PaymentUnavailable as error:
            raise _unavailable(container) from error

    @router.post("/billing/admin-grants", status_code=204)
    async def grant_admin(body: AdminGrantBody, request: Request) -> None:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            await billing.grant_admin(
                actor_is_admin=actor.view.is_admin,
                user_id=body.user_id,
                days=body.days,
                reason=body.reason,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error


def _body(view: BillingView) -> BillingBody:
    return BillingBody(
        premium=view.premium,
        access_until=view.access_until,
        price_stars=view.price_stars,
        period_days=view.period_days,
        gift_days=view.gift_days,
        trial_days=view.trial_days,
        assistant_questions=view.assistant_questions,
        subscription_payment_state=view.subscription_payment_state,
        gift_payment_state=view.gift_payment_state,
        subscription_state=view.subscription_state,
        auto_renew=view.auto_renew,
        subscription_order_id=view.subscription_order_id,
        subscription_invoice_link=view.subscription_invoice_link,
        gift_order_id=view.gift_order_id,
        gift_invoice_link=view.gift_invoice_link,
        gift_code=view.gift_code,
        gift_link=view.gift_link,
        trial_available=view.trial_available,
        period_end=view.period_end,
    )


def _field(container: Container, error: FieldInvalid) -> ApiError:
    status = 404 if error.message_key == "errors.not_found" else 422
    code = "not_found" if status == 404 else "validation_error"
    if error.message_key == "errors.unauthorized":
        status = 403
        code = "unauthorized"
    return ApiError(
        status,
        code,
        container.catalog.text(error.message_key),
        {error.field: error.message_key},
    )


def _unavailable(container: Container) -> ApiError:
    return ApiError(503, "unavailable", container.catalog.text("errors.payment_unavailable"))
