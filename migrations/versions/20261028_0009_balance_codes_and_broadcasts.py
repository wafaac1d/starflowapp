"""Balance gift codes and queued admin broadcasts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_0009"
down_revision: str | None = "20261028_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "balance_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_norm", sa.Text(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stars >= 1", name="balance_codes_stars_ck"),
        sa.CheckConstraint("max_uses >= 1", name="balance_codes_uses_ck"),
        sa.CheckConstraint("used_count >= 0", name="balance_codes_used_ck"),
        sa.CheckConstraint("used_count <= max_uses", name="balance_codes_left_ck"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_norm", name="balance_codes_norm_uq"),
    )
    op.create_table(
        "balance_code_redemptions",
        sa.Column("code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["code_id"], ["balance_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code_id", "user_id"),
    )
    op.create_table(
        "broadcasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("broadcasts_status_idx", "broadcasts", ["status", "created_at"])
    op.create_table(
        "broadcast_targets",
        sa.Column("broadcast_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["broadcast_id"], ["broadcasts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("broadcast_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("broadcast_targets")
    op.drop_index("broadcasts_status_idx", table_name="broadcasts")
    op.drop_table("broadcasts")
    op.drop_table("balance_code_redemptions")
    op.drop_table("balance_codes")
