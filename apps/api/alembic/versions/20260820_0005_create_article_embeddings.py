"""create local semantic search storage

Revision ID: 20260820_0005
Revises: 20260820_0004
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260820_0005"
down_revision = "20260820_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_article_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["knowledge_articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id"),
    )
    op.execute(
        "ALTER TABLE knowledge_article_embeddings "
        "ALTER COLUMN embedding TYPE vector(768) USING embedding::vector"
    )
    op.create_index(
        "ix_knowledge_article_embeddings_article_id",
        "knowledge_article_embeddings",
        ["article_id"],
    )
    op.execute(
        "CREATE INDEX ix_knowledge_article_embeddings_cosine "
        "ON knowledge_article_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_knowledge_article_embeddings_cosine")
    op.drop_index("ix_knowledge_article_embeddings_article_id", table_name="knowledge_article_embeddings")
    op.drop_table("knowledge_article_embeddings")
