"""create incidents

Revision ID: 20260820_0001
Revises:
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    incident_status = postgresql.ENUM(
        "new",
        "investigating",
        "awaiting_approval",
        "resolved",
        "closed",
        name="incident_status",
        create_type=False,
    )
    incident_severity = postgresql.ENUM(
        "low", "medium", "high", "critical", name="incident_severity", create_type=False
    )
    incident_status.create(op.get_bind(), checkfirst=True)
    incident_severity.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", incident_status, nullable=False),
        sa.Column("severity", incident_severity, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id"),
    )
    op.create_index("ix_incidents_incident_id", "incidents", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_incident_id", table_name="incidents")
    op.drop_table("incidents")
    sa.Enum(name="incident_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="incident_status").drop(op.get_bind(), checkfirst=True)
