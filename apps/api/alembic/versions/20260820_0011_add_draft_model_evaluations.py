"""add draft model evaluations

Revision ID: 20260820_0011
Revises: 20260820_0010
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0011"
down_revision = "20260820_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_status = postgresql.ENUM(
        "completed", "failed", name="draft_evaluation_run_status", create_type=False
    )
    review_decision = postgresql.ENUM(
        "grounded", "needs_human_review", name="grounding_review_decision", create_type=False
    )
    run_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "draft_evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expected_article_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id"),
    )
    op.create_index("ix_draft_evaluation_cases_evaluation_id", "draft_evaluation_cases", ["evaluation_id"])
    op.create_index("ix_draft_evaluation_cases_workspace_id", "draft_evaluation_cases", ["workspace_id"])
    op.create_table(
        "draft_evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("draft_body", sa.Text(), nullable=True),
        sa.Column("review_decision", review_decision, nullable=True),
        sa.Column("review_reason", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("human_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("human_score IS NULL OR (human_score >= 1 AND human_score <= 5)", name="ck_draft_evaluation_runs_human_score"),
        sa.ForeignKeyConstraint(["case_id"], ["draft_evaluation_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_draft_evaluation_runs_run_id", "draft_evaluation_runs", ["run_id"])
    op.create_index("ix_draft_evaluation_runs_case_id", "draft_evaluation_runs", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_draft_evaluation_runs_case_id", table_name="draft_evaluation_runs")
    op.drop_index("ix_draft_evaluation_runs_run_id", table_name="draft_evaluation_runs")
    op.drop_table("draft_evaluation_runs")
    op.drop_index("ix_draft_evaluation_cases_workspace_id", table_name="draft_evaluation_cases")
    op.drop_index("ix_draft_evaluation_cases_evaluation_id", table_name="draft_evaluation_cases")
    op.drop_table("draft_evaluation_cases")
    postgresql.ENUM(name="draft_evaluation_run_status").drop(op.get_bind(), checkfirst=True)
