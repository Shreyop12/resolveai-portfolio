"""add knowledge document timestamp defaults

Revision ID: 20260820_0016
Revises: 20260820_0015
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0016"
down_revision = "20260820_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("knowledge_documents", "created_at", server_default=sa.text("now()"))
    op.alter_column("knowledge_documents", "updated_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("knowledge_documents", "updated_at", server_default=None)
    op.alter_column("knowledge_documents", "created_at", server_default=None)
