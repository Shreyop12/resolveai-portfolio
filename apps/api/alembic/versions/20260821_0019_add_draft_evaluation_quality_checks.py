"""add draft evaluation quality checks

Revision ID: 20260821_0019
Revises: 20260821_0018
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0019"
down_revision = "20260821_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "draft_evaluation_runs",
        sa.Column("quality_decision", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "draft_evaluation_runs",
        sa.Column("quality_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_evaluation_runs", "quality_reason")
    op.drop_column("draft_evaluation_runs", "quality_decision")
