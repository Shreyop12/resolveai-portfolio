import uuid
from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIMENSIONS = 768


class KnowledgeArticleEmbedding(Base):
    """A local-model meaning vector for one published knowledge article."""

    __tablename__ = "knowledge_article_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_articles.id", ondelete="CASCADE"), unique=True, index=True
    )
    model: Mapped[str] = mapped_column(String(120))
    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
