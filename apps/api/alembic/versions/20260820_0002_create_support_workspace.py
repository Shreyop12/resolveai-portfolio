"""create support workspace tables

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0002"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ticket_status = postgresql.ENUM(
        "open",
        "drafting",
        "awaiting_review",
        "resolved",
        "closed",
        name="ticket_status",
        create_type=False,
    )
    ticket_priority = postgresql.ENUM(
        "low", "normal", "high", "urgent", name="ticket_priority", create_type=False
    )
    note_author = postgresql.ENUM(
        "support_agent", "system", name="note_author", create_type=False
    )
    for enum_type in (ticket_status, ticket_priority, note_author):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id"),
    )
    op.create_index("ix_support_tickets_ticket_id", "support_tickets", ["ticket_id"])
    op.create_index("ix_support_tickets_workspace_id", "support_tickets", ["workspace_id"])

    op.create_table(
        "ticket_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author", note_author, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_notes_ticket_id", "ticket_notes", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_notes_ticket_id", table_name="ticket_notes")
    op.drop_table("ticket_notes")
    op.drop_index("ix_support_tickets_workspace_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_ticket_id", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
    for enum_name in ("note_author", "ticket_priority", "ticket_status"):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
