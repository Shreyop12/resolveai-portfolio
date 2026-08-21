"""add ticket triage assessments

Revision ID: 20260820_0008
Revises: 20260820_0007
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0008"
down_revision = "20260820_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    decision = postgresql.ENUM(
        "draft_allowed", "human_escalation", name="triage_decision", create_type=False
    )
    category = postgresql.ENUM(
        "troubleshooting",
        "how_to",
        "account_or_billing",
        "security_or_privacy",
        "uncertain",
        name="triage_category",
        create_type=False,
    )
    decision.create(op.get_bind(), checkfirst=True)
    category.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ticket_triage_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.String(length=32), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("decision", decision, nullable=False),
        sa.Column("category", category, nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id"),
    )
    op.create_index(
        "ix_ticket_triage_assessments_assessment_id",
        "ticket_triage_assessments",
        ["assessment_id"],
    )
    op.create_index(
        "ix_ticket_triage_assessments_ticket_id",
        "ticket_triage_assessments",
        ["ticket_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_triage_assessments_ticket_id", table_name="ticket_triage_assessments")
    op.drop_index("ix_ticket_triage_assessments_assessment_id", table_name="ticket_triage_assessments")
    op.drop_table("ticket_triage_assessments")
    postgresql.ENUM(name="triage_category").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="triage_decision").drop(op.get_bind(), checkfirst=True)
