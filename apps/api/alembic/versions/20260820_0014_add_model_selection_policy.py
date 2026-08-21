"""add model selection policy

Revision ID: 20260820_0014
Revises: 20260820_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20260820_0014"
down_revision = "20260820_0013"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("model_selection_policies", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("workspace_id", sa.Uuid(), nullable=False), sa.Column("min_grounding_rate", sa.Float(), nullable=False), sa.Column("min_average_human_score", sa.Float(), nullable=False), sa.Column("max_average_latency_ms", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("workspace_id"))
    op.create_index("ix_model_selection_policies_workspace_id", "model_selection_policies", ["workspace_id"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_model_selection_policies_workspace_id", table_name="model_selection_policies")
    op.drop_table("model_selection_policies")
