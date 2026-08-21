import uuid
import hashlib
import re
from datetime import UTC, datetime

from app.models.knowledge import ArticleStatus, KnowledgeArticle, KnowledgeDocument
from app.models.workspace import Workspace
from app.repositories.knowledge import KnowledgeArticleRepository
from app.schemas.knowledge import KnowledgeArticleCreate


class InvalidArticleTransitionError(ValueError):
    """Raised when an article moves through an unsafe publication transition."""


ALLOWED_ARTICLE_TRANSITIONS: dict[ArticleStatus, set[ArticleStatus]] = {
    ArticleStatus.DRAFT: {ArticleStatus.PUBLISHED, ArticleStatus.ARCHIVED},
    ArticleStatus.PUBLISHED: {ArticleStatus.DRAFT, ArticleStatus.ARCHIVED},
    ArticleStatus.ARCHIVED: {ArticleStatus.DRAFT},
}


class KnowledgeArticleService:
    def __init__(self, repository: KnowledgeArticleRepository) -> None:
        self.repository = repository

    async def create(
        self, workspace: Workspace, payload: KnowledgeArticleCreate
    ) -> KnowledgeArticle:
        year = datetime.now(UTC).year
        article = KnowledgeArticle(
            article_id=f"KB-{year}-{uuid.uuid4().hex[:8].upper()}",
            workspace_id=workspace.id,
            title=payload.title,
            category=payload.category,
            body=payload.body,
            status=ArticleStatus.DRAFT,
        )
        return await self.repository.create(article)

    async def import_document(self, workspace: Workspace, source_file_name: str, category: str, content: str) -> KnowledgeDocument:
        title = source_file_name.rsplit(".", maxsplit=1)[0].replace("_", " ").replace("-", " ").strip() or "Imported support document"
        document = KnowledgeDocument(
            id=uuid.uuid4(),
            document_id=f"DOC-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
            workspace_id=workspace.id,
            title=title[:255],
            source_file_name=source_file_name,
            category=category,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
        chunks = [
            KnowledgeArticle(
                article_id=f"KB-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
                workspace_id=workspace.id,
                source_document_id=document.id,
                chunk_index=index,
                source_section=section,
                title=f"{title[:190]} — {section}"[:255],
                category=category,
                body=body,
                status=ArticleStatus.DRAFT,
            )
            for index, (section, body) in enumerate(split_document(content), start=1)
        ]
        document.chunk_count = len(chunks)
        return await self.repository.create_document(document, chunks)

    async def update_status(
        self, article: KnowledgeArticle, status: ArticleStatus
    ) -> KnowledgeArticle:
        if status == article.status:
            return article
        if status not in ALLOWED_ARTICLE_TRANSITIONS[article.status]:
            raise InvalidArticleTransitionError(
                f"Cannot transition {article.status} to {status}."
            )
        published_at = datetime.now(UTC) if status == ArticleStatus.PUBLISHED else None
        return await self.repository.update_status(article, status, published_at)


def split_document(content: str, max_chunk_characters: int = 3_500) -> list[tuple[str, str]]:
    """Create traceable, heading-aware chunks without splitting a paragraph when possible."""
    sections = re.split(r"(?m)^#{1,6}\s+(.+?)\s*$", content.strip())
    pairs: list[tuple[str, str]] = []
    if len(sections) == 1:
        pairs.append(("Document", sections[0]))
    else:
        introduction = sections[0].strip()
        if introduction:
            pairs.append(("Introduction", introduction))
        for index in range(1, len(sections), 2):
            pairs.append((sections[index].strip() or "Document", sections[index + 1].strip()))
    result: list[tuple[str, str]] = []
    for section, body in pairs:
        current = ""
        for paragraph in re.split(r"\n\s*\n", body):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if current and len(current) + len(paragraph) + 2 > max_chunk_characters:
                result.append((section, current))
                current = ""
            while len(paragraph) > max_chunk_characters:
                result.append((section, paragraph[:max_chunk_characters]))
                paragraph = paragraph[max_chunk_characters:]
            current = f"{current}\n\n{paragraph}".strip()
        if current:
            result.append((section, current))
    return result or [("Document", content.strip())]
