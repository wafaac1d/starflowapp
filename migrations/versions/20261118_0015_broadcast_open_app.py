"""Remember whether a broadcast includes the app button.

Revision ID: 20261118_0015
Revises: 20261105_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261118_0015"
down_revision: str | None = "20261105_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "broadcasts",
        sa.Column("open_app", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("broadcasts", "open_app")
