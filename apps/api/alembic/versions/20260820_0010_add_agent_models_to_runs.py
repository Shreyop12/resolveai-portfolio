"""add agent model map to coordinator runs

Revision ID: 20260820_0010
Revises: 20260820_0009
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0010"
down_revision = "20260820_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coordinator_runs",
        sa.Column(
            "agent_models",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("coordinator_runs", "agent_models")
