"""Referral star credits, affirmation keeps, and a separate reminder flag.

Revision ID: 20261103_0013
Revises: 20261101_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261103_0013"
down_revision: str | None = "20261101_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "star_credits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 1", name="star_credits_amount_ck"),
        sa.CheckConstraint("char_length(subject) BETWEEN 1 AND 80", name="star_credits_subject_ck"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "reason", "subject", name="star_credits_once_uq"),
    )
    op.create_table(
        "affirmation_keeps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(card_id) BETWEEN 1 AND 80",
            name="affirmation_keeps_card_ck",
        ),
        sa.CheckConstraint(
            "char_length(text) BETWEEN 1 AND 500",
            name="affirmation_keeps_text_ck",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "card_id", name="affirmation_keeps_card_uq"),
    )
    op.add_column(
        "notification_settings",
        sa.Column(
            "affirmation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "affirmation_enabled")
    op.drop_table("affirmation_keeps")
    op.drop_table("star_credits")
