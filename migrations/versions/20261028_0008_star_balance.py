"""Star balance and one-time spends for natal, compatibility and questions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_0008"
down_revision: str | None = "20261022_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("star_balance", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("users_star_balance_ck", "users", "star_balance >= 0")
    op.create_table(
        "star_spends",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 1", name="star_spends_amount_ck"),
        sa.CheckConstraint(
            "char_length(subject) BETWEEN 1 AND 120",
            name="star_spends_subject_ck",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "feature", "subject", name="star_spends_once_uq"),
    )


def downgrade() -> None:
    op.drop_table("star_spends")
    op.drop_constraint("users_star_balance_ck", "users", type_="check")
    op.drop_column("users", "star_balance")
