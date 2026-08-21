"""create approved knowledge article table

Revision ID: 20260820_0003
Revises: 20260820_0002
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0003"
down_revision = "20260820_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    article_status = postgresql.ENUM(
        "draft", "published", "archived", name="article_status", create_type=False
    )
    article_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", article_status, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id"),
    )
    op.create_index("ix_knowledge_articles_article_id", "knowledge_articles", ["article_id"])
    op.create_index(
        "ix_knowledge_articles_workspace_id", "knowledge_articles", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_articles_workspace_id", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_articles_article_id", table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
    postgresql.ENUM(name="article_status").drop(op.get_bind(), checkfirst=True)
