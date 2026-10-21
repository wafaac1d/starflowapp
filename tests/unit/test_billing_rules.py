from pathlib import Path
from uuid import uuid4

from starflow.cache.memory import MemoryCache
from starflow.domain.billing import (
    client_status_grants_access,
    payment_state,
    read_payload,
    reject_pre_checkout,
    sign_payload,
)
from starflow.i18n.catalog import load_catalog

ROOT = Path(__file__).resolve().parents[2]


def test_payload_signature_and_client_status() -> None:
    secret = "p" * 32
    order_id = uuid4()
    payload = sign_payload(order_id, secret)
    assert len(payload.encode()) <= 128
    assert read_payload(payload, secret) == order_id
    flipped = payload[:-1] + ("0" if payload[-1] != "0" else "1")
    assert read_payload(flipped, secret) is None
    assert client_status_grants_access("paid") is False
    assert (
        payment_state(
            server_paid=False,
            client_status="paid",
            order_status="open",
            sync_state="idle",
        )
        == "pending"
    )
    assert (
        payment_state(
            server_paid=True,
            client_status="cancelled",
            order_status="paid",
            sync_state="idle",
        )
        == "success"
    )
    assert reject_pre_checkout(
        order_found=True,
        signature_ok=False,
        user_matches=True,
        amount_matches=True,
        currency_ok=True,
        order_closed=False,
    )
    assert reject_pre_checkout(
        order_found=True,
        signature_ok=True,
        user_matches=False,
        amount_matches=True,
        currency_ok=True,
        order_closed=False,
    )
    assert not reject_pre_checkout(
        order_found=True,
        signature_ok=True,
        user_matches=True,
        amount_matches=True,
        currency_ok=True,
        order_closed=False,
    )


def test_invoice_copy_fits_telegram_limits() -> None:
    catalog = load_catalog(ROOT / "resources", "ru", MemoryCache(4))
    title = catalog.text("bot.invoice_subscription_title")
    gift = catalog.text("bot.invoice_gift_title")
    assert 1 <= len(title) <= 32
    assert 1 <= len(gift) <= 32
    assert 1 <= len(catalog.text("bot.invoice_subscription_description")) <= 255
    assert 1 <= len(catalog.text("bot.invoice_gift_description")) <= 255
