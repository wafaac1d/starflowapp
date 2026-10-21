"""Reserved quota, grant grace and idempotency keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0003"
down_revision: str | None = "20261021_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usage_counters",
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
    )
    op.drop_constraint("usage_counters_bounds_ck", "usage_counters", type_="check")
    op.create_check_constraint(
        "usage_counters_bounds_ck",
        "usage_counters",
        "used >= 0 AND reserved >= 0 AND used + reserved <= quota_limit",
    )
    op.alter_column("usage_counters", "reserved", server_default=None)
    op.add_column("subscriptions", sa.Column("grace_until", sa.DateTime(timezone=True)))
    op.add_column("subscriptions", sa.Column("revoked_at", sa.DateTime(timezone=True)))
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "idempotency_keys",
        sa.Column("id", uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="idempotency_keys_user_key_uq"),
        sa.CheckConstraint(
            "status IN ('reserved', 'committed', 'released')",
            name="idempotency_keys_status_ck",
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_column("subscriptions", "revoked_at")
    op.drop_column("subscriptions", "grace_until")
    op.drop_constraint("usage_counters_bounds_ck", "usage_counters", type_="check")
    op.drop_column("usage_counters", "reserved")
    op.create_check_constraint(
        "usage_counters_bounds_ck",
        "usage_counters",
        "used >= 0 AND used <= quota_limit",
    )
