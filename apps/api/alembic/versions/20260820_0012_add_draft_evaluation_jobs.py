"""add durable background jobs for draft evaluations

Revision ID: 20260820_0012
Revises: 20260820_0011
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0012"
down_revision = "20260820_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    job_status = sa.Enum(
        "queued", "running", "completed", "failed", name="draft_evaluation_job_status"
    )
    op.create_table(
        "draft_evaluation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["draft_evaluation_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draft_evaluation_jobs_job_id", "draft_evaluation_jobs", ["job_id"], unique=True)
    op.create_index("ix_draft_evaluation_jobs_case_id", "draft_evaluation_jobs", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_draft_evaluation_jobs_case_id", table_name="draft_evaluation_jobs")
    op.drop_index("ix_draft_evaluation_jobs_job_id", table_name="draft_evaluation_jobs")
    op.drop_table("draft_evaluation_jobs")
    sa.Enum(name="draft_evaluation_job_status").drop(op.get_bind(), checkfirst=True)
