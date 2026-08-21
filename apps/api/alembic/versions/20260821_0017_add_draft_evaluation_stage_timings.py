"""add draft evaluation stage timings

Revision ID: 20260821_0017
Revises: 20260820_0016
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0017"
down_revision = "20260820_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "draft_evaluation_runs",
        sa.Column("draft_generation_latency_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "draft_evaluation_runs",
        sa.Column("grounding_review_latency_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_evaluation_runs", "grounding_review_latency_ms")
    op.drop_column("draft_evaluation_runs", "draft_generation_latency_ms")
