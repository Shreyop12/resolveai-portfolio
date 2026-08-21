"""add ticket grounding reviews

Revision ID: 20260820_0009
Revises: 20260820_0008
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0009"
down_revision = "20260820_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    decision = postgresql.ENUM(
        "grounded", "needs_human_review", name="grounding_review_decision", create_type=False
    )
    decision.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ticket_grounding_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.String(length=32), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("decision", decision, nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("source_article_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["ticket_drafts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id"),
    )
    op.create_index("ix_ticket_grounding_reviews_review_id", "ticket_grounding_reviews", ["review_id"])
    op.create_index("ix_ticket_grounding_reviews_ticket_id", "ticket_grounding_reviews", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_grounding_reviews_ticket_id", table_name="ticket_grounding_reviews")
    op.drop_index("ix_ticket_grounding_reviews_review_id", table_name="ticket_grounding_reviews")
    op.drop_table("ticket_grounding_reviews")
    postgresql.ENUM(name="grounding_review_decision").drop(op.get_bind(), checkfirst=True)
