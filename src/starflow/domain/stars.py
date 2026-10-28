"""Внутренний баланс звёзд. Клиентский статус счёта его не меняет."""

from dataclasses import dataclass

from starflow.astro.ecliptic import SIGNS
from starflow.domain.billing import MAX_STARS

NATAL_STARS = 40
COMPATIBILITY_STARS = 40
QUESTION_STARS = 20
TOPUP_PRESETS = (10, 20, 50, 100)
MIN_TOPUP = 1

PRICES = {
    "natal": NATAL_STARS,
    "compatibility": COMPATIBILITY_STARS,
    "assistant": QUESTION_STARS,
}


def price_of(feature: str) -> int:
    found = PRICES.get(feature)
    if found is None:
        raise ValueError(feature)
    return found


def topup_amount_ok(amount: int) -> bool:
    return MIN_TOPUP <= amount <= MAX_STARS


def subject_ok(value: str) -> bool:
    if not 1 <= len(value) <= 120:
        return False
    return all(character.isalnum() or character in {":", "-", "_"} for character in value)


def pair_subject(left: str, right: str) -> str:
    parts = tuple(sorted(part.casefold().strip() for part in (left, right)))
    if parts[0] not in SIGNS or parts[1] not in SIGNS:
        raise ValueError("sign")
    return f"{parts[0]}:{parts[1]}"


def purchase_effect(kind: str) -> str:
    if kind == "topup":
        return "balance"
    if kind == "subscription":
        return "premium"
    return "gift"


@dataclass(frozen=True)
class SpendResult:
    allowed: bool
    charged: bool
    balance: int
    price: int


def settle_spend(balance: int, price: int, already: bool) -> SpendResult:
    if already:
        return SpendResult(allowed=True, charged=False, balance=balance, price=price)
    if balance < price:
        return SpendResult(allowed=False, charged=False, balance=balance, price=price)
    return SpendResult(allowed=True, charged=True, balance=balance - price, price=price)
