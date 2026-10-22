"""Notification kinds, outbox lease and blocked recipients."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0007"
down_revision: str | None = "20261022_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "notification_settings",
        sa.Column("day_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "notification_settings",
        sa.Column("moon_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "notification_settings",
        sa.Column("retro_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("event_key", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE notification_outbox SET event_key = local_date::text WHERE event_key = ''")
    op.drop_constraint("notification_outbox_once_uq", "notification_outbox", type_="unique")
    op.create_unique_constraint(
        "notification_outbox_event_uq",
        "notification_outbox",
        ["user_id", "kind", "event_key"],
    )


def downgrade() -> None:
    op.drop_constraint("notification_outbox_event_uq", "notification_outbox", type_="unique")
    op.create_unique_constraint(
        "notification_outbox_once_uq",
        "notification_outbox",
        ["user_id", "kind", "local_date"],
    )
    op.drop_column("notification_outbox", "leased_until")
    op.drop_column("notification_outbox", "event_key")
    op.drop_column("notification_settings", "retro_enabled")
    op.drop_column("notification_settings", "moon_enabled")
    op.drop_column("notification_settings", "day_enabled")
    op.drop_column("users", "is_blocked")
