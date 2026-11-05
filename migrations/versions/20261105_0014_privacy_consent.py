"""Store the privacy policy version accepted at registration.

Revision ID: 20261105_0014
Revises: 20261103_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261105_0014"
down_revision: str | None = "20261103_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("profiles", sa.Column("privacy_policy_version", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "privacy_policy_version")
    op.drop_column("profiles", "privacy_accepted_at")
