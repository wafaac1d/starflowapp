from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class User:
    id: UUID
    telegram_id: int
    username: str | None
    language_code: str | None
    referral_code: str | None = None
    referred_by: UUID | None = None


@dataclass(frozen=True)
class ProfileDraft:
    display_name: str
    birth_date: date | None
    birth_time: time | None
    birth_time_unknown: bool
    birth_place: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    timezone: str


@dataclass(frozen=True)
class Profile:
    id: UUID
    user_id: UUID
    display_name: str | None
    birth_date: date | None
    birth_time: time | None
    birth_time_unknown: bool
    birth_place: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    timezone: str | None
    onboarding_step: str
    streak_count: int = 0
    streak_last_date: date | None = None


@dataclass(frozen=True)
class PlaceHit:
    label: str
    latitude: Decimal
    longitude: Decimal


@dataclass(frozen=True)
class Order:
    id: UUID
    user_id: UUID | None
    invoice_payload: str


@dataclass(frozen=True)
class PaymentCharge:
    id: UUID
    order_id: UUID
    user_id: UUID | None
    telegram_payment_charge_id: str
    amount_stars: int


@dataclass(frozen=True)
class OutboxJob:
    id: UUID
    telegram_id: int
    text_key: str


@dataclass(frozen=True)
class UsageCounter:
    id: UUID
    user_id: UUID
    counter_key: str
    used: int
    reserved: int
    quota_limit: int
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True)
class RelatedBirth:
    id: UUID
    display_name: str
    birth_date: date | None


@dataclass(frozen=True)
class IdempotencyRecord:
    id: UUID
    user_id: UUID
    key: str
    feature: str
    status: str
    result: dict[str, object] | None
