from __future__ import annotations

import re
import uuid
from datetime import datetime
from math import sqrt

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import ArticleStatus, KnowledgeArticle, KnowledgeDocument
from app.models.embedding import KnowledgeArticleEmbedding

_TEST_STOP_WORDS = {"and", "are", "after", "before", "for", "from", "into", "not", "our", "the", "this", "that", "with", "you"}


class KnowledgeArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, article: KnowledgeArticle) -> KnowledgeArticle:
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def create_document(self, document: KnowledgeDocument, chunks: list[KnowledgeArticle]) -> KnowledgeDocument:
        self.session.add(document)
        # Chunks reference the source document by foreign key, so PostgreSQL
        # must receive the document row before the section rows.
        await self.session.flush()
        self.session.add_all(chunks)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def list_documents(self, workspace_id: uuid.UUID) -> list[KnowledgeDocument]:
        result = await self.session.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.workspace_id == workspace_id)
            .order_by(KnowledgeDocument.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, workspace_id: uuid.UUID, document_id: str) -> KnowledgeDocument | None:
        result = await self.session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.document_id == document_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_document_chunks(self, document_id: uuid.UUID) -> list[KnowledgeArticle]:
        result = await self.session.execute(
            select(KnowledgeArticle)
            .where(KnowledgeArticle.source_document_id == document_id)
            .order_by(KnowledgeArticle.chunk_index)
        )
        return list(result.scalars().all())

    async def publish_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        now = datetime.now().astimezone()
        document.status = ArticleStatus.PUBLISHED
        document.published_at = now
        chunks = await self.list_document_chunks(document.id)
        for chunk in chunks:
            chunk.status = ArticleStatus.PUBLISHED
            chunk.published_at = now
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def delete_draft_document(self, document: KnowledgeDocument) -> None:
        chunks = await self.list_document_chunks(document.id)
        for chunk in chunks:
            await self.session.delete(chunk)
        await self.session.delete(document)
        await self.session.commit()

    async def list(
        self,
        *,
        workspace_id: uuid.UUID,
        status: ArticleStatus | None,
        limit: int,
        offset: int,
    ) -> list[KnowledgeArticle]:
        statement = (
            select(KnowledgeArticle)
            .where(KnowledgeArticle.workspace_id == workspace_id)
            .order_by(KnowledgeArticle.updated_at.desc())
        )
        if status is not None:
            statement = statement.where(KnowledgeArticle.status == status)
        result = await self.session.execute(statement.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def get_by_article_id(
        self, *, workspace_id: uuid.UUID, article_id: str
    ) -> KnowledgeArticle | None:
        result = await self.session.execute(
            select(KnowledgeArticle).where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.article_id == article_id,
            )
        )
        return result.scalar_one_or_none()

    async def search_published(
        self, *, workspace_id: uuid.UUID, query: str, limit: int
    ) -> list[tuple[KnowledgeArticle, float]]:
        """Return published workspace articles ordered by keyword relevance."""
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            return await self._search_postgresql(workspace_id, query, limit)
        return await self._search_test_database(workspace_id, query, limit)

    async def _search_postgresql(
        self, workspace_id: uuid.UUID, query: str, limit: int
    ) -> list[tuple[KnowledgeArticle, float]]:
        document = func.to_tsvector(
            "english",
            KnowledgeArticle.title
            + " "
            + KnowledgeArticle.category
            + " "
            + KnowledgeArticle.body,
        )
        search_terms = func.plainto_tsquery("english", query)
        rank = func.ts_rank(document, search_terms).label("score")
        statement = (
            select(KnowledgeArticle, rank)
            .where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.status == ArticleStatus.PUBLISHED,
                document.op("@@")(search_terms),
            )
            .order_by(rank.desc(), KnowledgeArticle.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [(article, float(score)) for article, score in result.all()]

    async def _search_test_database(
        self, workspace_id: uuid.UUID, query: str, limit: int
    ) -> list[tuple[KnowledgeArticle, float]]:
        """Small SQLite-compatible equivalent used only by automated tests."""
        terms = [
            term
            for term in re.findall(r"[a-z0-9]+", query.lower())
            if len(term) >= 3 and term not in _TEST_STOP_WORDS
        ]
        if not terms:
            return []
        title = func.lower(KnowledgeArticle.title)
        category = func.lower(KnowledgeArticle.category)
        body = func.lower(KnowledgeArticle.body)
        matches = [
            or_(title.like(f"%{term}%"), category.like(f"%{term}%"), body.like(f"%{term}%"))
            for term in terms
        ]
        score = sum(
            (
                case((title.like(f"%{term}%"), 5), else_=0)
                + case((category.like(f"%{term}%"), 3), else_=0)
                + case((body.like(f"%{term}%"), 1), else_=0)
            )
            for term in terms
        ).label("score")
        statement = (
            select(KnowledgeArticle, score)
            .where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.status == ArticleStatus.PUBLISHED,
                or_(*matches),
            )
            .order_by(score.desc(), KnowledgeArticle.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [(article, float(score)) for article, score in result.all()]

    async def upsert_embedding(
        self, *, article: KnowledgeArticle, model: str, embedding: list[float]
    ) -> KnowledgeArticleEmbedding:
        result = await self.session.execute(
            select(KnowledgeArticleEmbedding).where(
                KnowledgeArticleEmbedding.article_id == article.id
            )
        )
        stored = result.scalar_one_or_none()
        if stored is None:
            stored = KnowledgeArticleEmbedding(
                article_id=article.id, model=model, embedding=embedding
            )
            self.session.add(stored)
        else:
            stored.model = model
            stored.embedding = embedding
        await self.session.commit()
        await self.session.refresh(stored)
        return stored

    async def delete_embedding(self, article: KnowledgeArticle) -> None:
        result = await self.session.execute(
            select(KnowledgeArticleEmbedding).where(
                KnowledgeArticleEmbedding.article_id == article.id
            )
        )
        stored = result.scalar_one_or_none()
        if stored is not None:
            await self.session.delete(stored)
            await self.session.commit()

    async def list_published(self, *, workspace_id: uuid.UUID) -> list[KnowledgeArticle]:
        result = await self.session.execute(
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.status == ArticleStatus.PUBLISHED,
            )
            .order_by(KnowledgeArticle.updated_at.desc())
        )
        return list(result.scalars().all())

    async def search_semantic(
        self, *, workspace_id: uuid.UUID, embedding: list[float], limit: int
    ) -> list[tuple[KnowledgeArticle, float]]:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            distance = KnowledgeArticleEmbedding.embedding.cosine_distance(embedding)
            similarity = (1 - distance).label("score")
            statement = (
                select(KnowledgeArticle, similarity)
                .join(
                    KnowledgeArticleEmbedding,
                    KnowledgeArticleEmbedding.article_id == KnowledgeArticle.id,
                )
                .where(
                    KnowledgeArticle.workspace_id == workspace_id,
                    KnowledgeArticle.status == ArticleStatus.PUBLISHED,
                )
                .order_by(distance)
                .limit(limit)
            )
            result = await self.session.execute(statement)
            return [(article, float(score)) for article, score in result.all()]

        result = await self.session.execute(
            select(KnowledgeArticle, KnowledgeArticleEmbedding)
            .join(
                KnowledgeArticleEmbedding,
                KnowledgeArticleEmbedding.article_id == KnowledgeArticle.id,
            )
            .where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.status == ArticleStatus.PUBLISHED,
            )
        )
        matches = [
            (article, self._cosine_similarity(embedding, stored.embedding))
            for article, stored in result.all()
        ]
        return sorted(matches, key=lambda item: item[1], reverse=True)[:limit]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        denominator = sqrt(sum(value * value for value in left)) * sqrt(
            sum(value * value for value in right)
        )
        if denominator == 0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / denominator

    async def update_status(
        self,
        article: KnowledgeArticle,
        status: ArticleStatus,
        published_at: datetime | None,
    ) -> KnowledgeArticle:
        article.status = status
        article.published_at = published_at
        await self.session.commit()
        await self.session.refresh(article)
        return article
