"""Consent flag for a related profile."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0006"
down_revision: str | None = "20261021_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "related_profiles",
        sa.Column("consent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("related_profiles", "consent")
