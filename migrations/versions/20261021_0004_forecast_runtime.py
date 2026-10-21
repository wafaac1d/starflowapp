"""Cache hits, reading streak and referral code."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0004"
down_revision: str | None = "20261021_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "forecast_cache",
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("forecast_cache", "hits", server_default=None)
    op.add_column(
        "profiles",
        sa.Column("streak_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("profiles", "streak_count", server_default=None)
    op.add_column("profiles", sa.Column("streak_last_date", sa.Date()))
    op.add_column("users", sa.Column("referral_code", sa.Text()))
    op.create_unique_constraint("users_referral_code_uq", "users", ["referral_code"])
    op.add_column("users", sa.Column("referred_by", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "users_referred_by_fk",
        "users",
        "users",
        ["referred_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("users_referred_by_fk", "users", type_="foreignkey")
    op.drop_column("users", "referred_by")
    op.drop_constraint("users_referral_code_uq", "users", type_="unique")
    op.drop_column("users", "referral_code")
    op.drop_column("profiles", "streak_last_date")
    op.drop_column("profiles", "streak_count")
    op.drop_column("forecast_cache", "hits")
