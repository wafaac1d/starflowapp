"""Счёт Stars. Закрытие invoice и клиентский status доступ не открывают."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

SUBSCRIPTION_PERIOD_SEC = 2592000
PAYLOAD_LIMIT = 128
MAX_STARS = 10000
INVOICE_STATUSES = frozenset({"paid", "cancelled", "failed", "pending"})
GIFT_FAILURE_LIMIT = 8
LINK_CLAIM_SEC = 30


def client_status_grants_access(status: str | None) -> bool:
    """Статус openInvoice — подсказка интерфейса. Доступ он не даёт."""
    return False


def sign_payload(order_id: UUID, secret: str) -> str:
    body = str(order_id)
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    payload = f"{body}.{digest}"
    if not 1 <= len(payload.encode()) <= PAYLOAD_LIMIT:
        raise ValueError("invoice payload exceeds 128 bytes")
    return payload


def read_payload(payload: str, secret: str) -> UUID | None:
    if len(payload.encode()) > PAYLOAD_LIMIT or payload.count(".") != 1:
        return None
    body, digest = payload.split(".", 1)
    if len(digest) != 32:
        return None
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(digest, expected):
        return None
    try:
        parsed = UUID(body)
    except ValueError:
        return None
    if str(parsed) != body:
        return None
    return parsed


def reject_pre_checkout(
    *,
    order_found: bool,
    signature_ok: bool,
    user_matches: bool,
    amount_matches: bool,
    currency_ok: bool,
    order_closed: bool,
) -> bool:
    if not order_found or not signature_ok or not user_matches:
        return True
    return not amount_matches or not currency_ok or order_closed


def payment_state(
    *,
    server_paid: bool,
    client_status: str | None,
    order_status: str | None,
    sync_state: str | None,
) -> str:
    if client_status_grants_access(client_status):
        raise RuntimeError("client invoice status must not grant premium")
    if server_paid:
        return "success"
    if sync_state == "creating_link" or order_status == "link_pending":
        return "pending"
    if client_status in {"paid", "pending"}:
        return "pending"
    if client_status == "cancelled":
        return "canceled"
    if client_status == "failed" or order_status == "link_failed" or sync_state == "link_failed":
        return "failed"
    return "none"


def subscription_state(*, active: bool, cancel_at_period_end: bool) -> str:
    if active and cancel_at_period_end:
        return "cancel_scheduled"
    if active:
        return "active"
    return "none"


@dataclass(frozen=True)
class OrderRecord:
    id: UUID
    user_id: UUID | None
    kind: str
    amount_stars: int
    currency: str
    status: str
    invoice_payload: str
    invoice_link: str | None
    client_status: str | None
    subscription_charge_id: str | None
    sync_state: str
    grant_id: UUID | None
    updated_at: datetime


@dataclass(frozen=True)
class ChargeRecord:
    id: UUID
    order_id: UUID
    user_id: UUID | None
    telegram_payment_charge_id: str
    amount_stars: int
    currency: str
    period_start: datetime
    period_end: datetime
    grant_id: UUID | None
    refunded_at: datetime | None
    is_recurring: bool
    is_first_recurring: bool


@dataclass(frozen=True)
class GrantRecord:
    id: UUID
    user_id: UUID
    source: str
    status: str
    period_start: datetime
    period_end: datetime
    grace_until: datetime | None
    revoked_at: datetime | None
    cancel_at_period_end: bool
    order_id: UUID | None
    telegram_charge_id: str | None


@dataclass(frozen=True)
class GiftRecord:
    id: UUID
    code: str
    purchaser_user_id: UUID | None
    status: str
    redeemed_at: datetime | None


@dataclass(frozen=True)
class SyncJob:
    kind: str
    order_id: UUID
    telegram_user_id: int
    charge_id: str
    is_canceled: bool
