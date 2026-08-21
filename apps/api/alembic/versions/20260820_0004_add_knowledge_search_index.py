"""add full-text index for published knowledge articles

Revision ID: 20260820_0004
Revises: 20260820_0003
Create Date: 2026-08-20 00:00:00
"""

from alembic import op

revision = "20260820_0004"
down_revision = "20260820_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_knowledge_articles_published_search
        ON knowledge_articles
        USING gin (to_tsvector('english', title || ' ' || category || ' ' || body))
        WHERE status = 'published'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_knowledge_articles_published_search")
