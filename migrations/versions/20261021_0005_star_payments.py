"""Orders, charges and gifts for Telegram Stars."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0005"
down_revision: str | None = "20261021_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("kind", sa.Text(), nullable=False, server_default="subscription"),
    )
    op.add_column("orders", sa.Column("subscription_period", sa.Integer()))
    op.add_column("orders", sa.Column("invoice_link", sa.Text()))
    op.add_column("orders", sa.Column("client_status", sa.Text()))
    op.add_column("orders", sa.Column("idempotency_key", sa.Text()))
    op.add_column("orders", sa.Column("subscription_charge_id", sa.Text()))
    op.add_column(
        "orders",
        sa.Column("sync_state", sa.Text(), nullable=False, server_default="idle"),
    )
    op.add_column("orders", sa.Column("grant_id", postgresql.UUID(as_uuid=True)))
    op.alter_column("orders", "kind", server_default=None)
    op.alter_column("orders", "sync_state", server_default=None)
    op.create_index(
        "orders_user_idempotency_uq",
        "orders",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.add_column("subscriptions", sa.Column("order_id", postgresql.UUID(as_uuid=True)))
    op.add_column("subscriptions", sa.Column("telegram_charge_id", sa.Text()))
    op.add_column(
        "subscriptions",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("subscriptions", "cancel_at_period_end", server_default=None)
    op.create_foreign_key(
        "subscriptions_order_id_fk",
        "subscriptions",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "orders_grant_id_fk",
        "orders",
        "subscriptions",
        ["grant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "payment_charges",
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "payment_charges",
        sa.Column("is_first_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "payment_charges",
        sa.Column("subscription_expiration", sa.DateTime(timezone=True)),
    )
    op.add_column("payment_charges", sa.Column("refunded_at", sa.DateTime(timezone=True)))
    op.add_column("payment_charges", sa.Column("refund_state", sa.Text()))
    op.add_column("payment_charges", sa.Column("grant_id", postgresql.UUID(as_uuid=True)))
    op.alter_column("payment_charges", "is_recurring", server_default=None)
    op.alter_column("payment_charges", "is_first_recurring", server_default=None)
    op.create_foreign_key(
        "payment_charges_grant_id_fk",
        "payment_charges",
        "subscriptions",
        ["grant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "subscription_events",
        "subscription_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_table(
        "gift_attempts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("gift_attempts")
    op.alter_column(
        "subscription_events",
        "subscription_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_constraint("payment_charges_grant_id_fk", "payment_charges", type_="foreignkey")
    op.drop_column("payment_charges", "grant_id")
    op.drop_column("payment_charges", "refund_state")
    op.drop_column("payment_charges", "refunded_at")
    op.drop_column("payment_charges", "subscription_expiration")
    op.drop_column("payment_charges", "is_first_recurring")
    op.drop_column("payment_charges", "is_recurring")
    op.drop_constraint("orders_grant_id_fk", "orders", type_="foreignkey")
    op.drop_constraint("subscriptions_order_id_fk", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "cancel_at_period_end")
    op.drop_column("subscriptions", "telegram_charge_id")
    op.drop_column("subscriptions", "order_id")
    op.drop_index("orders_user_idempotency_uq", table_name="orders")
    op.drop_column("orders", "grant_id")
    op.drop_column("orders", "sync_state")
    op.drop_column("orders", "subscription_charge_id")
    op.drop_column("orders", "idempotency_key")
    op.drop_column("orders", "client_status")
    op.drop_column("orders", "invoice_link")
    op.drop_column("orders", "subscription_period")
    op.drop_column("orders", "kind")
