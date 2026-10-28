"""Пополнение и списание баланса. Роутер только вызывает сценарий."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.errors import FieldInvalid, PaymentUnavailable
from starflow.domain.stars import pair_subject
from starflow.services.billing import TopupView


class BalanceBody(BaseModel):
    balance: int


class TopupRequest(BaseModel):
    amount: int = Field(ge=1, le=10000)


class TopupBody(BaseModel):
    order_id: UUID
    invoice_link: str
    balance: int
    amount: int


class SpendRequest(BaseModel):
    feature: str
    left_sign: str = ""
    right_sign: str = ""


class SpendBody(BaseModel):
    balance: int
    allowed: bool
    charged: bool
    price: int


class PremiumBuyBody(BaseModel):
    balance: int
    charged: bool


class CodeRedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class CodeRedeemBody(BaseModel):
    balance: int


def register_star_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")

    @router.get("/stars", response_model=BalanceBody)
    async def read_balance(request: Request) -> BalanceBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        balance = await container.stars_service.balance(actor.view.user_id)
        return BalanceBody(balance=balance)

    @router.post("/stars/topups", response_model=TopupBody)
    async def create_topup(
        body: TopupRequest,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> TopupBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            view = await container.billing_service.create_topup(
                actor.view.user_id,
                body.amount,
                idempotency_key,
            )
        except FieldInvalid as error:
            raise _field(container, error) from error
        except PaymentUnavailable as error:
            raise _unavailable(container) from error
        return _topup(view)

    @router.post("/stars/spends", response_model=SpendBody)
    async def spend(body: SpendRequest, request: Request) -> SpendBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            subject = _subject(body)
            result = await container.stars_service.buy(actor.view.user_id, body.feature, subject)
        except FieldInvalid as error:
            raise _field(container, error) from error
        except ValueError as error:
            raise _field(container, FieldInvalid("sign", "errors.validation")) from error
        if not result.allowed:
            raise ApiError(402, "stars_required", container.catalog.text("errors.stars_required"))
        return SpendBody(
            balance=result.balance,
            allowed=result.allowed,
            charged=result.charged,
            price=result.price,
        )

    @router.post("/stars/premium", response_model=PremiumBuyBody)
    async def buy_premium(
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> PremiumBuyBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            bought = await container.stars_service.buy_premium(
                actor.view.user_id,
                idempotency_key,
                container.settings.premium_price_stars,
                container.plans.premium.period_days,
            )
        except FieldInvalid as error:
            if error.message_key == "errors.stars_required":
                raise ApiError(
                    402,
                    "stars_required",
                    container.catalog.text("errors.stars_required"),
                ) from error
            raise _field(container, error) from error
        return PremiumBuyBody(balance=bought.balance, charged=bought.charged)

    @router.post("/stars/codes", response_model=CodeRedeemBody)
    async def redeem_code(body: CodeRedeemRequest, request: Request) -> CodeRedeemBody:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            balance = await container.stars_service.redeem_code(actor.view.user_id, body.code)
        except FieldInvalid as error:
            raise _field(container, error) from error
        return CodeRedeemBody(balance=balance)


def _subject(body: SpendRequest) -> str:
    if body.feature == "natal":
        return "self"
    if body.feature == "compatibility":
        return pair_subject(body.left_sign, body.right_sign)
    raise FieldInvalid("feature", "errors.validation")


def _topup(view: TopupView) -> TopupBody:
    return TopupBody(
        order_id=view.order_id,
        invoice_link=view.invoice_link,
        balance=view.balance,
        amount=view.amount,
    )


def _field(container: Container, error: FieldInvalid) -> ApiError:
    return ApiError(
        422,
        "validation_error",
        container.catalog.text(error.message_key),
        {error.field: error.message_key},
    )


def _unavailable(container: Container) -> ApiError:
    return ApiError(503, "unavailable", container.catalog.text("errors.payment_unavailable"))
