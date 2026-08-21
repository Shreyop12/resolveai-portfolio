"""add source documents and knowledge chunks

Revision ID: 20260820_0015
Revises: 20260820_0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260820_0015"
down_revision = "20260820_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "published", "archived", name="article_status", create_type=False), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_document_id", "knowledge_documents", ["document_id"], unique=True)
    op.create_index("ix_knowledge_documents_workspace_id", "knowledge_documents", ["workspace_id"], unique=False)
    op.add_column("knowledge_articles", sa.Column("source_document_id", sa.Uuid(), nullable=True))
    op.add_column("knowledge_articles", sa.Column("chunk_index", sa.Integer(), nullable=True))
    op.add_column("knowledge_articles", sa.Column("source_section", sa.String(length=255), nullable=True))
    op.create_foreign_key("fk_knowledge_articles_source_document_id", "knowledge_articles", "knowledge_documents", ["source_document_id"], ["id"])
    op.create_index("ix_knowledge_articles_source_document_id", "knowledge_articles", ["source_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_articles_source_document_id", table_name="knowledge_articles")
    op.drop_constraint("fk_knowledge_articles_source_document_id", "knowledge_articles", type_="foreignkey")
    op.drop_column("knowledge_articles", "source_section")
    op.drop_column("knowledge_articles", "chunk_index")
    op.drop_column("knowledge_articles", "source_document_id")
    op.drop_index("ix_knowledge_documents_workspace_id", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_document_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
