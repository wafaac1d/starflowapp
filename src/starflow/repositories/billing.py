"""Заказы, списания и подарки. Коммит остаётся у unit of work."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from starflow.db.tables import (
    GiftAttemptRow,
    GiftCodeRow,
    OrderRow,
    PaymentChargeRow,
    SubscriptionEventRow,
    SubscriptionRow,
    UserRow,
)
from starflow.domain.billing import (
    GIFT_FAILURE_LIMIT,
    ChargeRecord,
    GiftRecord,
    GrantRecord,
    OrderRecord,
    SyncJob,
)
from starflow.domain.entitlement import Grant
from starflow.domain.errors import Conflict
from starflow.domain.records import User


def _one_row(result: object) -> bool:
    count = getattr(result, "rowcount", 0)
    return isinstance(count, int) and count == 1


async def _save(session: AsyncSession, row: object) -> None:
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise Conflict("unique constraint rejected the write") from error
        raise


def _user(row: UserRow) -> User:
    return User(
        id=row.id,
        telegram_id=row.telegram_id,
        username=row.username,
        language_code=row.language_code,
        referral_code=row.referral_code,
        referred_by=row.referred_by,
    )


def _order(row: OrderRow) -> OrderRecord:
    return OrderRecord(
        id=row.id,
        user_id=row.user_id,
        kind=row.kind,
        amount_stars=row.amount_stars,
        currency=row.currency,
        status=row.status,
        invoice_payload=row.invoice_payload,
        invoice_link=row.invoice_link,
        client_status=row.client_status,
        subscription_charge_id=row.subscription_charge_id,
        sync_state=row.sync_state,
        grant_id=row.grant_id,
        updated_at=row.updated_at,
    )


def _charge(row: PaymentChargeRow) -> ChargeRecord:
    return ChargeRecord(
        id=row.id,
        order_id=row.order_id,
        user_id=row.user_id,
        telegram_payment_charge_id=row.telegram_payment_charge_id,
        amount_stars=row.amount_stars,
        currency=row.currency,
        period_start=row.period_start,
        period_end=row.period_end,
        grant_id=row.grant_id,
        refunded_at=row.refunded_at,
        is_recurring=row.is_recurring,
        is_first_recurring=row.is_first_recurring,
    )


def _grant_row(row: SubscriptionRow) -> GrantRecord:
    return GrantRecord(
        id=row.id,
        user_id=row.user_id,
        source=row.source,
        status=row.status,
        period_start=row.current_period_start,
        period_end=row.current_period_end,
        grace_until=row.grace_until,
        revoked_at=row.revoked_at,
        cancel_at_period_end=row.cancel_at_period_end,
        order_id=row.order_id,
        telegram_charge_id=row.telegram_charge_id,
    )


def _grant(row: SubscriptionRow) -> Grant:
    recorded = _grant_row(row)
    return Grant(
        id=recorded.id,
        user_id=recorded.user_id,
        source=recorded.source,
        status=recorded.status,
        period_start=recorded.period_start,
        period_end=recorded.period_end,
        grace_until=recorded.grace_until,
        revoked_at=recorded.revoked_at,
    )


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_user(self, user_id: UUID) -> User:
        result = await self._session.execute(
            select(UserRow).where(UserRow.id == user_id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.deleted_at is not None:
            raise Conflict("user is missing")
        return _user(row)

    async def lock_telegram(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(UserRow).where(UserRow.telegram_id == telegram_id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.deleted_at is not None:
            return None
        return _user(row)

    async def by_key(self, user_id: UUID, key: str) -> OrderRecord | None:
        result = await self._session.execute(
            select(OrderRow)
            .where(OrderRow.user_id == user_id, OrderRow.idempotency_key == key)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _order(row)

    async def latest_unpaid(self, user_id: UUID, kind: str) -> OrderRecord | None:
        result = await self._session.execute(
            select(OrderRow)
            .where(
                OrderRow.user_id == user_id,
                OrderRow.kind == kind,
                OrderRow.status.in_(("link_pending", "open", "link_failed")),
            )
            .order_by(OrderRow.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _order(row)

    async def insert_order(
        self,
        user_id: UUID,
        kind: str,
        amount: int,
        key: str,
        subscription_period: int | None,
        now: datetime,
    ) -> OrderRecord:
        row = OrderRow(
            user_id=user_id,
            plan_code="premium",
            amount_stars=amount,
            currency="XTR",
            status="link_pending",
            invoice_payload=f"hold-{uuid4()}",
            kind=kind,
            subscription_period=subscription_period,
            idempotency_key=key,
            sync_state="idle",
            created_at=now,
            updated_at=now,
        )
        await _save(self._session, row)
        return _order(row)

    async def set_payload(self, order_id: UUID, payload: str, now: datetime) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        row.invoice_payload = payload
        row.updated_at = now
        await self._session.flush()

    async def claim_link(self, order_id: UUID, now: datetime, stale_before: datetime) -> bool:
        result = await self._session.execute(
            update(OrderRow)
            .where(
                OrderRow.id == order_id,
                OrderRow.invoice_link.is_(None),
                or_(
                    OrderRow.sync_state.in_(("idle", "link_failed")),
                    (OrderRow.sync_state == "creating_link") & (OrderRow.updated_at < stale_before),
                ),
            )
            .values(sync_state="creating_link", status="link_pending", updated_at=now)
        )
        return _one_row(result)

    async def save_link(self, order_id: UUID, link: str, now: datetime) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        row.invoice_link = link
        row.status = "open"
        row.sync_state = "idle"
        row.updated_at = now
        await self._session.flush()

    async def mark_link_failed(self, order_id: UUID, now: datetime) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        row.status = "link_failed"
        row.sync_state = "link_failed"
        row.updated_at = now
        await self._session.flush()

    async def get_order(self, order_id: UUID) -> OrderRecord | None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            return None
        return _order(row)

    async def lock_order(self, order_id: UUID) -> OrderRecord | None:
        result = await self._session.execute(
            select(OrderRow).where(OrderRow.id == order_id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _order(row)

    async def set_client_status(self, order_id: UUID, status: str, now: datetime) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        row.client_status = status
        row.updated_at = now
        await self._session.flush()

    async def set_sync(self, order_id: UUID, state: str, now: datetime) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        row.sync_state = state
        row.updated_at = now
        await self._session.flush()

    async def mark_paid(self, order_id: UUID, now: datetime) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        row.status = "paid"
        row.updated_at = now
        await self._session.flush()

    async def remember_charge(self, order_id: UUID, charge_id: str, grant_id: UUID) -> None:
        row = await self._session.get(OrderRow, order_id)
        if row is None:
            raise Conflict("order is missing")
        if row.subscription_charge_id is None:
            row.subscription_charge_id = charge_id
        row.grant_id = grant_id
        await self._session.flush()

    async def charge_by_telegram(self, charge_id: str) -> ChargeRecord | None:
        result = await self._session.execute(
            select(PaymentChargeRow).where(PaymentChargeRow.telegram_payment_charge_id == charge_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _charge(row)

    async def lock_charge(self, charge_id: str) -> ChargeRecord | None:
        result = await self._session.execute(
            select(PaymentChargeRow)
            .where(PaymentChargeRow.telegram_payment_charge_id == charge_id)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _charge(row)

    async def insert_charge(
        self,
        order_id: UUID,
        user_id: UUID,
        charge_id: str,
        amount: int,
        currency: str,
        period_start: datetime,
        period_end: datetime,
        charged_at: datetime,
        payload: dict[str, object],
        *,
        is_recurring: bool,
        is_first_recurring: bool,
        expiration: datetime | None,
        grant_id: UUID | None,
    ) -> ChargeRecord:
        row = PaymentChargeRow(
            order_id=order_id,
            user_id=user_id,
            telegram_payment_charge_id=charge_id,
            amount_stars=amount,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
            charged_at=charged_at,
            provider_payload=payload,
            is_recurring=is_recurring,
            is_first_recurring=is_first_recurring,
            subscription_expiration=expiration,
            grant_id=grant_id,
        )
        await _save(self._session, row)
        return _charge(row)

    async def attach_grant(self, charge_row_id: UUID, grant_id: UUID) -> None:
        row = await self._session.get(PaymentChargeRow, charge_row_id)
        if row is None:
            raise Conflict("charge is missing")
        row.grant_id = grant_id
        await self._session.flush()

    async def subscription_charge_count(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(PaymentChargeRow)
            .join(OrderRow, OrderRow.id == PaymentChargeRow.order_id)
            .where(
                PaymentChargeRow.user_id == user_id,
                OrderRow.kind == "subscription",
                PaymentChargeRow.refunded_at.is_(None),
            )
        )
        return len(tuple(result.scalars()))

    async def other_charges(self, grant_id: UUID, charge_row_id: UUID) -> tuple[ChargeRecord, ...]:
        result = await self._session.execute(
            select(PaymentChargeRow).where(
                PaymentChargeRow.grant_id == grant_id,
                PaymentChargeRow.id != charge_row_id,
                PaymentChargeRow.refunded_at.is_(None),
            )
        )
        return tuple(_charge(row) for row in result.scalars())

    async def mark_refund_pending(self, charge_row_id: UUID) -> None:
        row = await self._session.get(PaymentChargeRow, charge_row_id)
        if row is None:
            raise Conflict("charge is missing")
        row.refund_state = "pending"
        await self._session.flush()

    async def mark_refunded(self, charge_row_id: UUID, now: datetime) -> None:
        row = await self._session.get(PaymentChargeRow, charge_row_id)
        if row is None:
            raise Conflict("charge is missing")
        row.refunded_at = now
        row.refund_state = None
        await self._session.flush()

    async def insert_grant(
        self,
        user_id: UUID,
        source: str,
        period_start: datetime,
        period_end: datetime,
        *,
        order_id: UUID | None = None,
        telegram_charge_id: str | None = None,
        grace_until: datetime | None = None,
    ) -> UUID:
        row = SubscriptionRow(
            user_id=user_id,
            plan_code="premium",
            status="active",
            current_period_start=period_start,
            current_period_end=period_end,
            grace_until=grace_until,
            source=source,
            order_id=order_id,
            telegram_charge_id=telegram_charge_id,
            cancel_at_period_end=False,
        )
        await _save(self._session, row)
        return row.id

    async def grants(self, user_id: UUID) -> tuple[Grant, ...]:
        result = await self._session.execute(
            select(SubscriptionRow).where(SubscriptionRow.user_id == user_id)
        )
        return tuple(_grant(row) for row in result.scalars())

    async def active_grant_rows(self) -> tuple[GrantRecord, ...]:
        result = await self._session.execute(
            select(SubscriptionRow).where(SubscriptionRow.status == "active")
        )
        return tuple(_grant_row(row) for row in result.scalars())

    async def has_source(self, user_id: UUID, source: str) -> bool:
        result = await self._session.execute(
            select(SubscriptionRow.id).where(
                SubscriptionRow.user_id == user_id,
                SubscriptionRow.source == source,
            )
        )
        return result.first() is not None

    async def subscription_flags(self, user_id: UUID) -> GrantRecord | None:
        result = await self._session.execute(
            select(SubscriptionRow)
            .where(
                SubscriptionRow.user_id == user_id,
                SubscriptionRow.source == "subscription",
                SubscriptionRow.status == "active",
            )
            .order_by(SubscriptionRow.current_period_end.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _grant_row(row)

    async def set_grace(self, grant_id: UUID, until: datetime) -> None:
        row = await self._session.get(SubscriptionRow, grant_id)
        if row is None:
            raise Conflict("grant is missing")
        row.grace_until = until
        row.updated_at = until
        await self._session.flush()

    async def expire(self, grant_id: UUID, now: datetime) -> None:
        row = await self._session.get(SubscriptionRow, grant_id)
        if row is None or row.status != "active":
            return
        row.status = "expired"
        row.updated_at = now
        await self._session.flush()
        await self.add_event(grant_id, row.user_id, "expired", {})

    async def revoke(self, grant_id: UUID, now: datetime) -> None:
        row = await self._session.get(SubscriptionRow, grant_id)
        if row is None:
            raise Conflict("grant is missing")
        row.status = "revoked"
        row.revoked_at = now
        row.updated_at = now
        await self._session.flush()

    async def set_period_end(self, grant_id: UUID, period_end: datetime) -> None:
        row = await self._session.get(SubscriptionRow, grant_id)
        if row is None:
            raise Conflict("grant is missing")
        row.current_period_end = period_end
        row.updated_at = period_end
        await self._session.flush()

    async def set_cancel(self, order_id: UUID, is_canceled: bool, now: datetime) -> UUID | None:
        result = await self._session.execute(
            select(SubscriptionRow).where(
                SubscriptionRow.order_id == order_id,
                SubscriptionRow.status == "active",
            )
        )
        latest: UUID | None = None
        for row in result.scalars():
            row.cancel_at_period_end = is_canceled
            row.updated_at = now
            latest = row.id
        await self._session.flush()
        return latest

    async def add_event(
        self,
        subscription_id: UUID | None,
        user_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        await _save(
            self._session,
            SubscriptionEventRow(
                subscription_id=subscription_id,
                user_id=user_id,
                event_type=event_type,
                payload=payload,
            ),
        )

    async def referral_recorded(self, referred_user_id: UUID) -> bool:
        result = await self._session.execute(
            select(SubscriptionEventRow.id).where(
                SubscriptionEventRow.event_type == "referral_reward",
                SubscriptionEventRow.payload["referred_user_id"].astext == str(referred_user_id),
            )
        )
        return result.first() is not None

    async def latest_order(self, user_id: UUID, kind: str) -> OrderRecord | None:
        result = await self._session.execute(
            select(OrderRow)
            .where(OrderRow.user_id == user_id, OrderRow.kind == kind)
            .order_by(OrderRow.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _order(row)

    async def order_has_charge(self, order_id: UUID) -> bool:
        result = await self._session.execute(
            select(PaymentChargeRow.id).where(PaymentChargeRow.order_id == order_id).limit(1)
        )
        return result.first() is not None

    async def latest_paid_subscription(self, user_id: UUID) -> OrderRecord | None:
        result = await self._session.execute(
            select(OrderRow)
            .where(
                OrderRow.user_id == user_id,
                OrderRow.kind == "subscription",
                OrderRow.status == "paid",
                OrderRow.subscription_charge_id.is_not(None),
            )
            .order_by(OrderRow.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _order(row)

    async def insert_gift(
        self,
        code: str,
        purchaser_user_id: UUID,
        charge_row_id: UUID,
    ) -> GiftRecord:
        row = GiftCodeRow(
            code=code,
            purchaser_user_id=purchaser_user_id,
            plan_code="premium",
            charge_id=charge_row_id,
            status="issued",
        )
        await _save(self._session, row)
        return GiftRecord(row.id, row.code, row.purchaser_user_id, row.status, row.redeemed_at)

    async def latest_gift_code(self, user_id: UUID) -> str | None:
        result = await self._session.execute(
            select(GiftCodeRow)
            .where(GiftCodeRow.purchaser_user_id == user_id, GiftCodeRow.status == "issued")
            .order_by(GiftCodeRow.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return row.code

    async def lock_gift(self, code: str) -> GiftRecord | None:
        result = await self._session.execute(
            select(GiftCodeRow).where(GiftCodeRow.code == code).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return GiftRecord(row.id, row.code, row.purchaser_user_id, row.status, row.redeemed_at)

    async def mark_redeemed(self, gift_id: UUID, user_id: UUID, now: datetime) -> bool:
        result = await self._session.execute(
            update(GiftCodeRow)
            .where(
                GiftCodeRow.id == gift_id,
                GiftCodeRow.status == "issued",
                GiftCodeRow.redeemed_at.is_(None),
            )
            .values(status="redeemed", recipient_user_id=user_id, redeemed_at=now)
        )
        return _one_row(result)

    async def gift_blocked(self, user_id: UUID, now: datetime) -> bool:
        row = await self._session.get(GiftAttemptRow, user_id)
        if row is None:
            return False
        if row.window_start < now - timedelta(hours=1):
            return False
        return row.failures >= GIFT_FAILURE_LIMIT

    async def note_failure(self, user_id: UUID, now: datetime) -> None:
        row = await self._session.get(GiftAttemptRow, user_id)
        if row is None:
            await _save(
                self._session,
                GiftAttemptRow(user_id=user_id, failures=1, window_start=now),
            )
            return
        if row.window_start < now - timedelta(hours=1):
            row.failures = 1
            row.window_start = now
        else:
            row.failures += 1
        await self._session.flush()

    async def sync_jobs(self) -> tuple[SyncJob, ...]:
        orders = await self._session.execute(
            select(OrderRow, UserRow.telegram_id)
            .join(UserRow, UserRow.id == OrderRow.user_id)
            .where(OrderRow.sync_state.in_(("cancel_pending", "resume_pending")))
        )
        jobs = [
            SyncJob(
                kind=row.sync_state,
                order_id=row.id,
                telegram_user_id=telegram_id,
                charge_id=row.subscription_charge_id or "",
                is_canceled=row.sync_state == "cancel_pending",
            )
            for row, telegram_id in orders.all()
            if row.subscription_charge_id
        ]
        refunds = await self._session.execute(
            select(PaymentChargeRow, UserRow.telegram_id)
            .join(UserRow, UserRow.id == PaymentChargeRow.user_id)
            .where(PaymentChargeRow.refund_state == "pending")
        )
        jobs.extend(
            SyncJob(
                kind="refund_pending",
                order_id=row.order_id,
                telegram_user_id=telegram_id,
                charge_id=row.telegram_payment_charge_id,
                is_canceled=False,
            )
            for row, telegram_id in refunds.all()
        )
        return tuple(jobs)
