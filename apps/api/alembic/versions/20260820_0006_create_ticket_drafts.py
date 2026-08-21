"""create human-reviewed ticket drafts

Revision ID: 20260820_0006
Revises: 20260820_0005
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0006"
down_revision = "20260820_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    draft_review_status = postgresql.ENUM(
        "awaiting_review", "approved", "rejected", name="draft_review_status", create_type=False
    )
    draft_review_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ticket_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.String(length=32), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_article_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coordinator_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", draft_review_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id"),
    )
    op.create_index("ix_ticket_drafts_draft_id", "ticket_drafts", ["draft_id"])
    op.create_index("ix_ticket_drafts_ticket_id", "ticket_drafts", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_drafts_ticket_id", table_name="ticket_drafts")
    op.drop_index("ix_ticket_drafts_draft_id", table_name="ticket_drafts")
    op.drop_table("ticket_drafts")
    postgresql.ENUM(name="draft_review_status").drop(op.get_bind(), checkfirst=True)
