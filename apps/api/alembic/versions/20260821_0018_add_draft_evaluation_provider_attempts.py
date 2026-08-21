"""add draft evaluation provider attempts

Revision ID: 20260821_0018
Revises: 20260821_0017
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0018"
down_revision = "20260821_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "draft_evaluation_runs",
        sa.Column("provider_attempts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("draft_evaluation_runs", "provider_attempts")
