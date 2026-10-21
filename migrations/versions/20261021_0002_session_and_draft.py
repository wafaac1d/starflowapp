"""Server sessions, onboarding draft and a stored start parameter."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0002"
down_revision: str | None = "20261021_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column("users", sa.Column("pending_start_param", sa.Text()))
    op.alter_column("profiles", "display_name", existing_type=sa.Text(), nullable=True)
    op.alter_column("profiles", "timezone", existing_type=sa.Text(), nullable=True)
    op.add_column(
        "profiles",
        sa.Column("onboarding_step", sa.Text(), nullable=False, server_default="welcome"),
    )
    op.create_check_constraint(
        "profiles_onboarding_step_ck",
        "profiles",
        "onboarding_step IN ('welcome', 'name', 'date', 'time', 'timezone', 'place', 'done')",
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("token_hash", name="auth_sessions_token_hash_uq"),
    )
    op.create_index("auth_sessions_user_idx", "auth_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("auth_sessions_user_idx", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_constraint("profiles_onboarding_step_ck", "profiles", type_="check")
    op.drop_column("profiles", "onboarding_step")
    op.alter_column("profiles", "timezone", existing_type=sa.Text(), nullable=False)
    op.alter_column("profiles", "display_name", existing_type=sa.Text(), nullable=False)
    op.drop_column("users", "pending_start_param")
