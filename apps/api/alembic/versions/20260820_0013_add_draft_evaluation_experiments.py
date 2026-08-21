"""add named draft evaluation experiments

Revision ID: 20260820_0013
Revises: 20260820_0012
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0013"
down_revision = "20260820_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "draft_evaluation_experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("case_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draft_evaluation_experiments_experiment_id", "draft_evaluation_experiments", ["experiment_id"], unique=True)
    op.create_index("ix_draft_evaluation_experiments_workspace_id", "draft_evaluation_experiments", ["workspace_id"], unique=False)
    op.add_column("draft_evaluation_jobs", sa.Column("experiment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_draft_evaluation_jobs_experiment_id", "draft_evaluation_jobs", "draft_evaluation_experiments", ["experiment_id"], ["id"]
    )
    op.create_index("ix_draft_evaluation_jobs_experiment_id", "draft_evaluation_jobs", ["experiment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_draft_evaluation_jobs_experiment_id", table_name="draft_evaluation_jobs")
    op.drop_constraint("fk_draft_evaluation_jobs_experiment_id", "draft_evaluation_jobs", type_="foreignkey")
    op.drop_column("draft_evaluation_jobs", "experiment_id")
    op.drop_index("ix_draft_evaluation_experiments_workspace_id", table_name="draft_evaluation_experiments")
    op.drop_index("ix_draft_evaluation_experiments_experiment_id", table_name="draft_evaluation_experiments")
    op.drop_table("draft_evaluation_experiments")
