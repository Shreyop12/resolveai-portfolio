"""add coordinator traces and retrieval evaluation cases

Revision ID: 20260820_0007
Revises: 20260820_0006
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0007"
down_revision = "20260820_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_status = postgresql.ENUM(
        "completed", "blocked", "failed", name="coordinator_run_status", create_type=False
    )
    run_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "coordinator_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("status", run_status, nullable=False),
        sa.Column("source_article_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("chat_model", sa.String(length=120), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["ticket_drafts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_coordinator_runs_run_id", "coordinator_runs", ["run_id"])
    op.create_index("ix_coordinator_runs_ticket_id", "coordinator_runs", ["ticket_id"])
    op.create_table(
        "retrieval_evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(length=1000), nullable=False),
        sa.Column("expected_article_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id"),
    )
    op.create_index("ix_retrieval_evaluation_cases_evaluation_id", "retrieval_evaluation_cases", ["evaluation_id"])
    op.create_index("ix_retrieval_evaluation_cases_workspace_id", "retrieval_evaluation_cases", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_evaluation_cases_workspace_id", table_name="retrieval_evaluation_cases")
    op.drop_index("ix_retrieval_evaluation_cases_evaluation_id", table_name="retrieval_evaluation_cases")
    op.drop_table("retrieval_evaluation_cases")
    op.drop_index("ix_coordinator_runs_ticket_id", table_name="coordinator_runs")
    op.drop_index("ix_coordinator_runs_run_id", table_name="coordinator_runs")
    op.drop_table("coordinator_runs")
    postgresql.ENUM(name="coordinator_run_status").drop(op.get_bind(), checkfirst=True)
