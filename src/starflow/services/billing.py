"""Сценарий Stars. Вызов Telegram не держит соединение с базой."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID

import structlog

from starflow.domain.billing import (
    LINK_CLAIM_SEC,
    SUBSCRIPTION_PERIOD_SEC,
    GrantRecord,
    OrderRecord,
    SyncJob,
    client_status_grants_access,
    payment_state,
    read_payload,
    reject_pre_checkout,
    sign_payload,
    subscription_state,
)
from starflow.domain.entitlement import Grant, access_end, grant_is_open
from starflow.domain.errors import Conflict, FieldInvalid, PaymentUnavailable
from starflow.domain.plans import Plans
from starflow.domain.quota import idempotency_key_ok
from starflow.domain.stars import purchase_effect, topup_amount_ok
from starflow.domain.time import now_utc
from starflow.i18n.catalog import Catalog
from starflow.repositories.billing import BillingRepository
from starflow.repositories.protocols import OutboxRepository
from starflow.services.stars import InvoiceDraft, StarGateway

_LOG = structlog.get_logger("billing")


class BillingStore(Protocol):
    billing: BillingRepository
    outbox: OutboxRepository

    async def commit(self) -> None: ...


class BillingWork(Protocol):
    async def __aenter__(self) -> BillingStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class BillingView:
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


@dataclass(frozen=True)
class TopupView:
    order_id: UUID
    invoice_link: str
    balance: int
    amount: int


class BillingService:
    def __init__(
        self,
        uow_factory: Callable[[], BillingWork],
        gateway: StarGateway,
        plans: Plans,
        secret: str,
        catalog: Catalog,
        mini_app_url: str,
        *,
        now: Callable[[], datetime] = now_utc,
    ) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway
        self._plans = plans
        self._secret = secret
        self._catalog = catalog
        self._mini_app_url = mini_app_url.rstrip("/")
        self._now = now

    async def view(self, user_id: UUID) -> BillingView:
        now = self._now()
        async with self._uow_factory() as uow:
            return await self._view(uow, user_id, now)

    async def create_invoice(self, user_id: UUID, kind: str, key: str) -> BillingView:
        if kind not in {"subscription", "gift"}:
            raise FieldInvalid("kind", "errors.validation")
        if not idempotency_key_ok(key):
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        now = self._now()
        order_id: UUID | None = None
        payload = ""
        async with self._uow_factory() as uow:
            await uow.billing.lock_user(user_id)
            if kind == "subscription" and await self._subscription_open(uow, user_id, now):
                return await self._view(uow, user_id, now)
            keyed = await uow.billing.by_key(user_id, key)
            reusable = keyed
            if reusable is None and kind == "subscription":
                reusable = await uow.billing.latest_unpaid(user_id, kind)
            price = self._plans.premium.price_stars
            if reusable is not None and reusable.amount_stars != price:
                fresh_claim = now - timedelta(seconds=LINK_CLAIM_SEC)
                busy = reusable.sync_state == "creating_link" and reusable.updated_at > fresh_claim
                if not busy and await uow.billing.replace_open_price(reusable.id, price, now):
                    refreshed = await uow.billing.get_order(reusable.id)
                    if refreshed is not None:
                        reusable = refreshed
            if reusable is not None and reusable.invoice_link:
                return await self._view(uow, user_id, now)
            fresh = now - timedelta(seconds=LINK_CLAIM_SEC)
            if (
                reusable is not None
                and reusable.sync_state == "creating_link"
                and reusable.updated_at > fresh
            ):
                return await self._view(uow, user_id, now)
            if reusable is None:
                reusable = await uow.billing.insert_order(
                    user_id,
                    kind,
                    self._plans.premium.price_stars,
                    key,
                    SUBSCRIPTION_PERIOD_SEC if kind == "subscription" else None,
                    now,
                )
                signed = sign_payload(reusable.id, self._secret)
                await uow.billing.set_payload(reusable.id, signed, now)
                payload = signed
            else:
                payload = reusable.invoice_payload
            claimed = await uow.billing.claim_link(reusable.id, now, fresh)
            if not claimed:
                await uow.commit()
                return await self._view(uow, user_id, now)
            order_id = reusable.id
            await uow.commit()
        if order_id is None:
            return await self.view(user_id)
        try:
            link = await self._gateway.create_invoice_link(self._draft(kind, payload))
        except Exception as error:
            _LOG.warning("invoice_link_failed", error_type=type(error).__name__)
            async with self._uow_factory() as uow:
                await uow.billing.mark_link_failed(order_id, self._now())
                await uow.commit()
            raise PaymentUnavailable("invoice link failed") from error
        async with self._uow_factory() as uow:
            await uow.billing.save_link(order_id, link, self._now())
            await uow.commit()
        return await self.view(user_id)

    async def create_topup(self, user_id: UUID, amount: int, key: str) -> TopupView:
        if not topup_amount_ok(amount):
            raise FieldInvalid("amount", "errors.validation")
        if not idempotency_key_ok(key):
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        now = self._now()
        order_id: UUID | None = None
        payload = ""
        async with self._uow_factory() as uow:
            await uow.billing.lock_user(user_id)
            existing = await uow.billing.by_key(user_id, key)
            if existing is not None and (
                existing.kind != "topup" or existing.amount_stars != amount
            ):
                raise FieldInvalid("idempotency_key", "errors.idempotency_key")
            if existing is not None and existing.invoice_link:
                balance = await uow.billing.star_balance(user_id)
                return TopupView(existing.id, existing.invoice_link, balance, amount)
            fresh = now - timedelta(seconds=LINK_CLAIM_SEC)
            if (
                existing is not None
                and existing.sync_state == "creating_link"
                and existing.updated_at > fresh
            ):
                raise PaymentUnavailable("invoice link is still opening")
            if existing is None:
                existing = await uow.billing.insert_order(
                    user_id,
                    "topup",
                    amount,
                    key,
                    None,
                    now,
                    plan_code="stars",
                )
                signed = sign_payload(existing.id, self._secret)
                await uow.billing.set_payload(existing.id, signed, now)
                payload = signed
            else:
                payload = existing.invoice_payload
            claimed = await uow.billing.claim_link(existing.id, now, fresh)
            if not claimed:
                await uow.commit()
                raise PaymentUnavailable("invoice link is still opening")
            order_id = existing.id
            await uow.commit()
        if order_id is None:
            raise PaymentUnavailable("invoice link is still opening")
        try:
            link = await self._gateway.create_invoice_link(self._draft("topup", payload, amount))
        except Exception as error:
            _LOG.warning("invoice_link_failed", error_type=type(error).__name__)
            async with self._uow_factory() as uow:
                await uow.billing.mark_link_failed(order_id, self._now())
                await uow.commit()
            raise PaymentUnavailable("invoice link failed") from error
        async with self._uow_factory() as uow:
            await uow.billing.save_link(order_id, link, self._now())
            balance = await uow.billing.star_balance(user_id)
            await uow.commit()
        return TopupView(order_id, link, balance, amount)

    async def note_client_status(self, user_id: UUID, order_id: UUID, status: str) -> BillingView:
        if status not in {"paid", "cancelled", "failed", "pending"}:
            raise FieldInvalid("status", "errors.validation")
        if client_status_grants_access(status):
            raise RuntimeError("client invoice status must not grant premium")
        now = self._now()
        async with self._uow_factory() as uow:
            order = await uow.billing.get_order(order_id)
            if order is None or order.user_id != user_id:
                raise FieldInvalid("order", "errors.not_found")
            await uow.billing.set_client_status(order_id, status, now)
            await uow.commit()
        return await self.view(user_id)

    async def pre_checkout(
        self,
        query_id: str,
        telegram_user_id: int,
        currency: str,
        total_amount: int,
        invoice_payload: str,
    ) -> None:
        message: str | None
        try:
            async with self._uow_factory() as uow:
                message = await self._checkout_message(
                    uow,
                    telegram_user_id,
                    currency,
                    total_amount,
                    invoice_payload,
                )
        except Exception as error:
            _LOG.warning("pre_checkout_failed", error_type=type(error).__name__)
            message = self._catalog.text("errors.payment_check")
        await self._gateway.answer_pre_checkout(query_id, message is None, message)

    async def apply_payment(
        self,
        *,
        telegram_user_id: int,
        currency: str,
        total_amount: int,
        invoice_payload: str,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str,
        is_recurring: bool,
        is_first_recurring: bool,
        subscription_expiration_date: int | None,
    ) -> None:
        try:
            await self._apply_payment(
                telegram_user_id=telegram_user_id,
                currency=currency,
                total_amount=total_amount,
                invoice_payload=invoice_payload,
                telegram_payment_charge_id=telegram_payment_charge_id,
                provider_payment_charge_id=provider_payment_charge_id,
                is_recurring=is_recurring,
                is_first_recurring=is_first_recurring,
                subscription_expiration_date=subscription_expiration_date,
            )
        except Conflict:
            async with self._uow_factory() as uow:
                existing = await uow.billing.charge_by_telegram(telegram_payment_charge_id)
            if existing is None:
                raise

    async def set_canceled(self, user_id: UUID, is_canceled: bool) -> BillingView:
        now = self._now()
        async with self._uow_factory() as uow:
            user = await uow.billing.lock_user(user_id)
            order = await uow.billing.latest_paid_subscription(user_id)
            if order is None or order.subscription_charge_id is None:
                raise FieldInvalid("subscription", "errors.payment_check")
            desired = "cancel_pending" if is_canceled else "resume_pending"
            if order.sync_state == desired:
                return await self._view(uow, user_id, now)
            await uow.billing.set_sync(order.id, desired, now)
            await uow.commit()
            telegram_id = user.telegram_id
            charge_id = order.subscription_charge_id
            order_id = order.id
        try:
            await self._gateway.edit_user_star_subscription(telegram_id, charge_id, is_canceled)
        except Exception as error:
            _LOG.warning("subscription_edit_failed", error_type=type(error).__name__)
            raise PaymentUnavailable("subscription edit failed") from error
        await self._finish_cancel(order_id, user_id, is_canceled)
        return await self.view(user_id)

    async def refund(
        self,
        *,
        actor_is_admin: bool,
        charge_id: str,
        confirm: bool,
        reason: str,
    ) -> None:
        if not actor_is_admin:
            raise FieldInvalid("admin", "errors.unauthorized")
        if not confirm or not reason.strip():
            raise FieldInvalid("confirm", "errors.payment_confirm")
        now = self._now()
        async with self._uow_factory() as uow:
            charge = await uow.billing.lock_charge(charge_id)
            if charge is None or charge.user_id is None:
                raise FieldInvalid("charge", "errors.not_found")
            if charge.refunded_at is not None:
                return
            user = await uow.billing.lock_user(charge.user_id)
            await uow.billing.mark_refund_pending(charge.id)
            await uow.billing.set_sync(charge.order_id, "refund_pending", now)
            await uow.billing.add_event(
                charge.grant_id,
                user.id,
                "refund_requested",
                {"charge_id": charge_id, "reason": reason.strip()},
            )
            await uow.commit()
            telegram_id = user.telegram_id
        try:
            await self._gateway.refund_star_payment(telegram_id, charge_id)
        except Exception as error:
            _LOG.warning("refund_failed", error_type=type(error).__name__)
            raise PaymentUnavailable("refund failed") from error
        await self._finish_refund(charge_id, reason.strip())

    async def start_trial(self, user_id: UUID) -> BillingView:
        if not self._plans.trial.once:
            raise RuntimeError("trial must be one-time")
        now = self._now()
        end = now + timedelta(days=self._plans.trial.days)
        async with self._uow_factory() as uow:
            await uow.billing.lock_user(user_id)
            if await uow.billing.has_source(user_id, "trial"):
                raise FieldInvalid("trial", "errors.trial_used")
            grant_id = await uow.billing.insert_grant(user_id, "trial", now, end)
            await uow.billing.add_event(grant_id, user_id, "trial", {})
            await uow.commit()
        return await self.view(user_id)

    async def grant_admin(
        self,
        *,
        actor_is_admin: bool,
        user_id: UUID,
        days: int,
        reason: str,
        confirm: bool,
    ) -> None:
        if not actor_is_admin:
            raise FieldInvalid("admin", "errors.unauthorized")
        if not confirm or not reason.strip() or days < 1 or days > 366:
            raise FieldInvalid("reason", "errors.payment_confirm")
        now = self._now()
        async with self._uow_factory() as uow:
            await uow.billing.lock_user(user_id)
            grant_id = await uow.billing.insert_grant(
                user_id,
                "admin",
                now,
                now + timedelta(days=days),
            )
            await uow.billing.add_event(
                grant_id,
                user_id,
                "admin_grant",
                {"reason": reason.strip(), "days": days},
            )
            await uow.commit()

    async def redeem(self, user_id: UUID, code: str) -> BillingView:
        cleaned = code.strip()
        now = self._now()
        async with self._uow_factory() as uow:
            await uow.billing.lock_user(user_id)
            if await uow.billing.gift_blocked(user_id, now):
                raise FieldInvalid("code", "errors.gift_invalid")
            if len(cleaned) < 16 or len(cleaned) > 80:
                await uow.billing.note_failure(user_id, now)
                await uow.commit()
                raise FieldInvalid("code", "errors.gift_invalid")
            gift = await uow.billing.lock_gift(cleaned)
            if gift is None or gift.status != "issued" or gift.redeemed_at is not None:
                await uow.billing.note_failure(user_id, now)
                await uow.commit()
                raise FieldInvalid("code", "errors.gift_invalid")
            if gift.purchaser_user_id == user_id:
                raise FieldInvalid("code", "errors.gift_self")
            redeemed = await uow.billing.mark_redeemed(gift.id, user_id, now)
            if not redeemed:
                await uow.billing.note_failure(user_id, now)
                await uow.commit()
                raise FieldInvalid("code", "errors.gift_invalid")
            grant_id = await uow.billing.insert_grant(
                user_id,
                "gift",
                now,
                now + timedelta(days=self._plans.gift.days),
            )
            await uow.billing.add_event(
                grant_id,
                user_id,
                "gift_redeemed",
                {"gift_id": str(gift.id)},
            )
            await uow.commit()
        return await self.view(user_id)

    async def maintain(self) -> None:
        now = self._now()
        async with self._uow_factory() as uow:
            grants = await uow.billing.active_grant_rows()
            for grant in grants:
                await self._touch(uow, grant, now)
            jobs = await uow.billing.sync_jobs()
            await uow.commit()
        for job in jobs:
            await self._reconcile(job)

    async def _apply_payment(
        self,
        *,
        telegram_user_id: int,
        currency: str,
        total_amount: int,
        invoice_payload: str,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str,
        is_recurring: bool,
        is_first_recurring: bool,
        subscription_expiration_date: int | None,
    ) -> None:
        now = self._now()
        order_id = read_payload(invoice_payload, self._secret)
        async with self._uow_factory() as uow:
            if await uow.billing.charge_by_telegram(telegram_payment_charge_id):
                return
            user = await uow.billing.lock_telegram(telegram_user_id)
            order = await uow.billing.lock_order(order_id) if order_id is not None else None
            if user is None or order is None or order.user_id != user.id:
                _LOG.warning("payment_rejected")
                return
            closed = order.status == "link_failed" or (
                order.kind == "topup" and order.status == "paid"
            )
            if reject_pre_checkout(
                order_found=True,
                signature_ok=True,
                user_matches=True,
                amount_matches=total_amount == order.amount_stars,
                currency_ok=currency == "XTR" and order.currency == "XTR",
                order_closed=closed,
            ):
                _LOG.warning("payment_rejected")
                return
            if purchase_effect(order.kind) == "balance":
                await uow.billing.insert_charge(
                    order.id,
                    user.id,
                    telegram_payment_charge_id,
                    total_amount,
                    currency,
                    now,
                    now,
                    now,
                    {
                        "provider_payment_charge_id": provider_payment_charge_id,
                        "is_recurring": is_recurring,
                        "is_first_recurring": is_first_recurring,
                        "subscription_expiration_date": subscription_expiration_date,
                    },
                    is_recurring=False,
                    is_first_recurring=False,
                    expiration=None,
                    grant_id=None,
                )
                await uow.billing.credit_stars(user.id, total_amount)
                await uow.billing.mark_paid(order.id, now)
                await uow.commit()
                return
            expiration = _expiration(subscription_expiration_date)
            if order.kind == "subscription" and expiration is not None:
                period_end = expiration
            elif order.kind == "subscription":
                period_end = now + timedelta(days=self._plans.premium.period_days)
            else:
                period_end = now + timedelta(days=self._plans.gift.days)
            charge = await uow.billing.insert_charge(
                order.id,
                user.id,
                telegram_payment_charge_id,
                total_amount,
                currency,
                now,
                period_end,
                now,
                {
                    "provider_payment_charge_id": provider_payment_charge_id,
                    "is_recurring": is_recurring,
                    "is_first_recurring": is_first_recurring,
                    "subscription_expiration_date": subscription_expiration_date,
                },
                is_recurring=is_recurring,
                is_first_recurring=is_first_recurring,
                expiration=expiration,
                grant_id=None,
            )
            if order.kind == "subscription":
                grant_id = await uow.billing.insert_grant(
                    user.id,
                    "subscription",
                    now,
                    period_end,
                    order_id=order.id,
                    telegram_charge_id=telegram_payment_charge_id,
                )
                await uow.billing.attach_grant(charge.id, grant_id)
                await uow.billing.remember_charge(
                    order.id,
                    order.subscription_charge_id or telegram_payment_charge_id,
                    grant_id,
                )
                await uow.billing.add_event(
                    grant_id,
                    user.id,
                    "payment",
                    {
                        "charge_id": telegram_payment_charge_id,
                        "is_recurring": is_recurring,
                        "is_first_recurring": is_first_recurring,
                    },
                )
                await self._reward_referrer(uow, user.id, user.referred_by, now)
            else:
                code = secrets.token_urlsafe(18)
                gift = await uow.billing.insert_gift(code, user.id, charge.id)
                await uow.billing.add_event(
                    None,
                    user.id,
                    "gift_issued",
                    {"gift_id": str(gift.id)},
                )
            await uow.billing.mark_paid(order.id, now)
            await uow.commit()

    async def _reward_referrer(
        self,
        uow: BillingStore,
        referred_user_id: UUID,
        referrer_id: UUID | None,
        now: datetime,
    ) -> None:
        if referrer_id is None:
            return
        if await uow.billing.subscription_charge_count(referred_user_id) != 1:
            return
        if await uow.billing.referral_recorded(referred_user_id):
            return
        grant_id = await uow.billing.insert_grant(
            referrer_id,
            "referral",
            now,
            now + timedelta(days=self._plans.referral.reward_days),
        )
        await uow.billing.add_event(
            grant_id,
            referrer_id,
            "referral_reward",
            {"referred_user_id": str(referred_user_id)},
        )

    async def _checkout_message(
        self,
        uow: BillingStore,
        telegram_user_id: int,
        currency: str,
        total_amount: int,
        invoice_payload: str,
    ) -> str | None:
        order_id = read_payload(invoice_payload, self._secret)
        order = await uow.billing.get_order(order_id) if order_id is not None else None
        user = await uow.billing.lock_telegram(telegram_user_id)
        closed = False
        if order is not None:
            closed = order.status == "link_failed" or (
                order.kind in {"gift", "topup"} and order.status == "paid"
            )
        rejected = reject_pre_checkout(
            order_found=order is not None,
            signature_ok=order_id is not None,
            user_matches=user is not None and order is not None and order.user_id == user.id,
            amount_matches=order is not None and total_amount == order.amount_stars,
            currency_ok=currency == "XTR" and (order is None or order.currency == "XTR"),
            order_closed=closed,
        )
        if rejected:
            return self._catalog.text("errors.payment_check")
        return None

    async def _finish_cancel(self, order_id: UUID, user_id: UUID, is_canceled: bool) -> None:
        now = self._now()
        async with self._uow_factory() as uow:
            grant_id = await uow.billing.set_cancel(order_id, is_canceled, now)
            await uow.billing.set_sync(order_id, "synced", now)
            await uow.billing.add_event(
                grant_id,
                user_id,
                "cancel" if is_canceled else "resume",
                {"is_canceled": is_canceled},
            )
            await uow.commit()

    async def _finish_refund(self, charge_id: str, reason: str) -> None:
        now = self._now()
        async with self._uow_factory() as uow:
            charge = await uow.billing.lock_charge(charge_id)
            if charge is None or charge.user_id is None:
                return
            if charge.refunded_at is None:
                await uow.billing.mark_refunded(charge.id, now)
                order = await uow.billing.get_order(charge.order_id)
                if (
                    order is not None
                    and purchase_effect(order.kind) == "balance"
                    and charge.user_id is not None
                ):
                    await uow.billing.debit_stars(charge.user_id, charge.amount_stars)
            if charge.grant_id is not None:
                others = await uow.billing.other_charges(charge.grant_id, charge.id)
                if others:
                    await uow.billing.set_period_end(
                        charge.grant_id,
                        max(item.period_end for item in others),
                    )
                else:
                    await uow.billing.revoke(charge.grant_id, now)
            await uow.billing.set_sync(charge.order_id, "synced", now)
            await uow.billing.add_event(
                charge.grant_id,
                charge.user_id,
                "refunded",
                {"charge_id": charge_id, "reason": reason},
            )
            await uow.commit()

    async def _touch(self, uow: BillingStore, grant: GrantRecord, now: datetime) -> None:
        grace = timedelta(hours=self._plans.premium.grace_hours)
        waiting = grant.source == "subscription" and not grant.cancel_at_period_end
        if waiting and grant.period_end <= now < grant.period_end + grace:
            if grant.grace_until is None:
                await uow.billing.set_grace(grant.id, grant.period_end + grace)
            return
        if grant.cancel_at_period_end or grant.source != "subscription":
            end = grant.period_end
        elif grant.grace_until is not None and grant.grace_until > grant.period_end:
            end = grant.grace_until
        else:
            end = grant.period_end
        if now >= end:
            await uow.billing.expire(grant.id, now)
            return
        remind_from = grant.period_end - timedelta(days=self._plans.premium.reminder_days)
        if grant.source == "subscription" and grant.cancel_at_period_end and remind_from <= now:
            try:
                await uow.outbox.enqueue(
                    grant.user_id,
                    "subscription_ending",
                    "bot.subscription_ending",
                    grant.period_end.date(),
                    now,
                )
            except Conflict:
                return

    async def _reconcile(self, job: SyncJob) -> None:
        try:
            if job.kind == "refund_pending":
                await self._gateway.refund_star_payment(job.telegram_user_id, job.charge_id)
            else:
                await self._gateway.edit_user_star_subscription(
                    job.telegram_user_id,
                    job.charge_id,
                    job.is_canceled,
                )
        except Exception as error:
            _LOG.warning("billing_reconcile_failed", error_type=type(error).__name__)
            return
        if job.kind == "refund_pending":
            await self._finish_refund(job.charge_id, "reconcile")
            return
        async with self._uow_factory() as uow:
            order = await uow.billing.get_order(job.order_id)
            user_id = None if order is None else order.user_id
        if user_id is None:
            return
        await self._finish_cancel(job.order_id, user_id, job.is_canceled)

    async def _subscription_open(self, uow: BillingStore, user_id: UUID, now: datetime) -> bool:
        flags = await uow.billing.subscription_flags(user_id)
        if flags is None:
            return False
        return grant_is_open(_as_grant(flags), now)

    async def _view(self, uow: BillingStore, user_id: UUID, now: datetime) -> BillingView:
        grants = await uow.billing.grants(user_id)
        subscription = await uow.billing.latest_order(user_id, "subscription")
        gift = await uow.billing.latest_order(user_id, "gift")
        code = await uow.billing.latest_gift_code(user_id)
        flags = await uow.billing.subscription_flags(user_id)
        trial_used = await uow.billing.has_source(user_id, "trial")
        subscription_paid = subscription is not None and await uow.billing.order_has_charge(
            subscription.id
        )
        gift_paid = gift is not None and await uow.billing.order_has_charge(gift.id)
        active = flags is not None and grant_is_open(_as_grant(flags), now)
        state = subscription_state(
            active=active,
            cancel_at_period_end=flags is not None and flags.cancel_at_period_end,
        )
        link = f"{self._mini_app_url}?startapp=gift_{code}" if code and self._mini_app_url else None
        return BillingView(
            premium=access_end(grants, now) is not None,
            access_until=access_end(grants, now),
            price_stars=self._plans.premium.price_stars,
            period_days=self._plans.premium.period_days,
            gift_days=self._plans.gift.days,
            trial_days=self._plans.trial.days,
            assistant_questions=self._plans.premium.assistant_questions,
            subscription_payment_state=_order_state(subscription, subscription_paid),
            gift_payment_state=_order_state(gift, gift_paid),
            subscription_state=state,
            auto_renew=state == "active",
            subscription_order_id=None if subscription is None else subscription.id,
            subscription_invoice_link=_payable_link(subscription),
            gift_order_id=None if gift is None else gift.id,
            gift_invoice_link=_payable_link(gift),
            gift_code=code,
            gift_link=link,
            trial_available=not trial_used,
            period_end=None if flags is None else flags.period_end,
        )

    def _draft(self, kind: str, payload: str, amount: int | None = None) -> InvoiceDraft:
        if kind == "topup":
            return InvoiceDraft(
                title=self._catalog.text("bot.invoice_topup_title"),
                description=self._catalog.text("bot.invoice_topup_description"),
                payload=payload,
                amount=0 if amount is None else amount,
                label="stars",
                subscription_period=None,
            )
        if kind == "subscription":
            return InvoiceDraft(
                title=self._catalog.text("bot.invoice_subscription_title"),
                description=self._catalog.text("bot.invoice_subscription_description"),
                payload=payload,
                amount=self._plans.premium.price_stars,
                label="premium",
                subscription_period=SUBSCRIPTION_PERIOD_SEC,
            )
        return InvoiceDraft(
            title=self._catalog.text("bot.invoice_gift_title"),
            description=self._catalog.text("bot.invoice_gift_description"),
            payload=payload,
            amount=self._plans.premium.price_stars,
            label="premium",
            subscription_period=None,
        )


def _as_grant(row: GrantRecord) -> Grant:
    return Grant(
        id=row.id,
        user_id=row.user_id,
        source=row.source,
        status=row.status,
        period_start=row.period_start,
        period_end=row.period_end,
        grace_until=row.grace_until,
        revoked_at=row.revoked_at,
    )


def _payable_link(order: OrderRecord | None) -> str | None:
    if order is None or order.status == "paid":
        return None
    return order.invoice_link


def _order_state(order: OrderRecord | None, server_paid: bool) -> str:
    if order is None:
        return "none"
    return payment_state(
        server_paid=server_paid,
        client_status=order.client_status,
        order_status=order.status,
        sync_state=order.sync_state,
    )


def _expiration(stamp: int | None) -> datetime | None:
    if stamp is None:
        return None
    return datetime.fromtimestamp(stamp, UTC)
