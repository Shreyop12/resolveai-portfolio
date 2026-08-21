import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.knowledge import ArticleStatus


class KnowledgeArticleCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    category: str = Field(min_length=2, max_length=80)
    body: str = Field(min_length=20, max_length=100_000)


class KnowledgeDocumentImport(BaseModel):
    source_file_name: str = Field(min_length=3, max_length=255)
    category: str = Field(min_length=2, max_length=80)
    content: str = Field(min_length=20, max_length=100_000)


class KnowledgeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    title: str
    source_file_name: str
    category: str
    status: ArticleStatus
    chunk_count: int
    created_at: datetime


class KnowledgeDocumentList(BaseModel):
    items: list[KnowledgeDocumentRead]


class ArticleStatusUpdate(BaseModel):
    status: ArticleStatus


class KnowledgeArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article_id: str
    title: str
    category: str
    body: str
    status: ArticleStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeArticleList(BaseModel):
    items: list[KnowledgeArticleRead]
    limit: int
    offset: int


class KnowledgeSearchResult(KnowledgeArticleRead):
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    items: list[KnowledgeSearchResult]


class KnowledgeReindexResponse(BaseModel):
    indexed: int
    model: str


class HybridSearchResult(KnowledgeArticleRead):
    fusion_score: float
    keyword_rank: int | None
    semantic_rank: int | None


class HybridSearchResponse(BaseModel):
    query: str
    fusion_method: str
    items: list[HybridSearchResult]
