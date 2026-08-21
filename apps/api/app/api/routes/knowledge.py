import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.support import require_workspace
from app.db.session import get_session
from app.models.knowledge import ArticleStatus
from app.repositories.knowledge import KnowledgeArticleRepository
from app.schemas.knowledge import (
    ArticleStatusUpdate,
    KnowledgeArticleCreate,
    KnowledgeDocumentImport,
    KnowledgeDocumentList,
    KnowledgeDocumentRead,
    KnowledgeArticleList,
    KnowledgeArticleRead,
    HybridSearchResponse,
    HybridSearchResult,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeReindexResponse,
)
from app.services.embeddings import (
    EmbeddingClient,
    EmbeddingProviderError,
    article_embedding_text,
    get_embedding_client,
)
from app.services.knowledge import InvalidArticleTransitionError, KnowledgeArticleService
from app.services.hybrid_search import fuse_ranked_results

router = APIRouter(prefix="/workspaces/{workspace_slug}/knowledge-articles", tags=["knowledge base"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
EmbeddingClientDependency = Annotated[EmbeddingClient, Depends(get_embedding_client)]


async def require_article(
    workspace_id: uuid.UUID, article_id: str, session: AsyncSession
):
    article = await KnowledgeArticleRepository(session).get_by_article_id(
        workspace_id=workspace_id, article_id=article_id
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge article not found.")
    return article


@router.post("", response_model=KnowledgeArticleRead, status_code=status.HTTP_201_CREATED)
async def create_article(
    workspace_slug: str, payload: KnowledgeArticleCreate, session: SessionDependency
) -> KnowledgeArticleRead:
    workspace = await require_workspace(workspace_slug, session)
    return await KnowledgeArticleService(KnowledgeArticleRepository(session)).create(
        workspace, payload
    )


@router.post("/documents/import-text", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
async def import_text_document(
    workspace_slug: str, payload: KnowledgeDocumentImport, session: SessionDependency
) -> KnowledgeDocumentRead:
    """Ingest a locally selected TXT/MD document into reviewable, searchable chunks."""
    if not payload.source_file_name.lower().endswith((".txt", ".md", ".markdown")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only TXT and Markdown documents are supported.")
    workspace = await require_workspace(workspace_slug, session)
    return await KnowledgeArticleService(KnowledgeArticleRepository(session)).import_document(
        workspace, payload.source_file_name, payload.category, payload.content
    )


@router.get("/documents", response_model=KnowledgeDocumentList)
async def list_documents(workspace_slug: str, session: SessionDependency) -> KnowledgeDocumentList:
    workspace = await require_workspace(workspace_slug, session)
    return KnowledgeDocumentList(items=await KnowledgeArticleRepository(session).list_documents(workspace.id))


@router.patch("/documents/{document_id}/publish", response_model=KnowledgeDocumentRead)
async def publish_document(
    workspace_slug: str, document_id: str, session: SessionDependency, embedding_client: EmbeddingClientDependency
) -> KnowledgeDocumentRead:
    workspace = await require_workspace(workspace_slug, session)
    repository = KnowledgeArticleRepository(session)
    document = await repository.get_document(workspace.id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found.")
    if document.status != ArticleStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft documents can be published.")
    chunks = await repository.list_document_chunks(document.id)
    try:
        for chunk in chunks:
            await repository.upsert_embedding(
                article=chunk, model=embedding_client.model_name, embedding=await embedding_client.embed(article_embedding_text(chunk))
            )
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return await repository.publish_document(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft_document(
    workspace_slug: str, document_id: str, session: SessionDependency
) -> Response:
    workspace = await require_workspace(workspace_slug, session)
    repository = KnowledgeArticleRepository(session)
    document = await repository.get_document(workspace.id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found.")
    if document.status != ArticleStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft documents can be deleted.")
    await repository.delete_draft_document(document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=KnowledgeArticleList)
async def list_articles(
    workspace_slug: str,
    session: SessionDependency,
    status_filter: ArticleStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> KnowledgeArticleList:
    workspace = await require_workspace(workspace_slug, session)
    articles = await KnowledgeArticleRepository(session).list(
        workspace_id=workspace.id, status=status_filter, limit=limit, offset=offset
    )
    return KnowledgeArticleList(items=articles, limit=limit, offset=offset)


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_articles(
    workspace_slug: str,
    session: SessionDependency,
    q: str = Query(min_length=2, max_length=1_000),
    limit: int = Query(default=5, ge=1, le=20),
) -> KnowledgeSearchResponse:
    workspace = await require_workspace(workspace_slug, session)
    results = await KnowledgeArticleRepository(session).search_published(
        workspace_id=workspace.id, query=q, limit=limit
    )
    return KnowledgeSearchResponse(
        query=q,
        items=[
            KnowledgeSearchResult(
                **KnowledgeArticleRead.model_validate(article).model_dump(), score=score
            )
            for article, score in results
        ],
    )


@router.get("/semantic-search", response_model=KnowledgeSearchResponse)
async def semantic_search_articles(
    workspace_slug: str,
    session: SessionDependency,
    embedding_client: EmbeddingClientDependency,
    q: str = Query(min_length=2, max_length=1_000),
    limit: int = Query(default=5, ge=1, le=20),
) -> KnowledgeSearchResponse:
    workspace = await require_workspace(workspace_slug, session)
    try:
        query_embedding = await embedding_client.embed(q)
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    results = await KnowledgeArticleRepository(session).search_semantic(
        workspace_id=workspace.id, embedding=query_embedding, limit=limit
    )
    return KnowledgeSearchResponse(
        query=q,
        items=[
            KnowledgeSearchResult(
                **KnowledgeArticleRead.model_validate(article).model_dump(), score=score
            )
            for article, score in results
        ],
    )


@router.get("/hybrid-search", response_model=HybridSearchResponse)
async def hybrid_search_articles(
    workspace_slug: str,
    session: SessionDependency,
    embedding_client: EmbeddingClientDependency,
    q: str = Query(min_length=2, max_length=1_000),
    limit: int = Query(default=5, ge=1, le=20),
) -> HybridSearchResponse:
    workspace = await require_workspace(workspace_slug, session)
    try:
        query_embedding = await embedding_client.embed(q)
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    repository = KnowledgeArticleRepository(session)
    candidate_limit = max(limit * 4, 20)
    keyword_results = await repository.search_published(
        workspace_id=workspace.id, query=q, limit=candidate_limit
    )
    semantic_results = await repository.search_semantic(
        workspace_id=workspace.id, embedding=query_embedding, limit=candidate_limit
    )
    matches = fuse_ranked_results(keyword_results, semantic_results, limit=limit)
    return HybridSearchResponse(
        query=q,
        fusion_method="reciprocal_rank_fusion",
        items=[
            HybridSearchResult(
                **KnowledgeArticleRead.model_validate(match.article).model_dump(),
                fusion_score=match.fusion_score,
                keyword_rank=match.keyword_rank,
                semantic_rank=match.semantic_rank,
            )
            for match in matches
        ],
    )
@router.post("/reindex", response_model=KnowledgeReindexResponse)
async def reindex_published_articles(
    workspace_slug: str,
    session: SessionDependency,
    embedding_client: EmbeddingClientDependency,
) -> KnowledgeReindexResponse:
    workspace = await require_workspace(workspace_slug, session)
    repository = KnowledgeArticleRepository(session)
    articles = await repository.list_published(workspace_id=workspace.id)
    try:
        for article in articles:
            await repository.upsert_embedding(
                article=article,
                model=embedding_client.model_name,
                embedding=await embedding_client.embed(article_embedding_text(article)),
            )
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return KnowledgeReindexResponse(indexed=len(articles), model=embedding_client.model_name)


@router.get("/{article_id}", response_model=KnowledgeArticleRead)
async def get_article(
    workspace_slug: str, article_id: str, session: SessionDependency
) -> KnowledgeArticleRead:
    workspace = await require_workspace(workspace_slug, session)
    return await require_article(workspace.id, article_id, session)


@router.patch("/{article_id}/status", response_model=KnowledgeArticleRead)
async def update_article_status(
    workspace_slug: str,
    article_id: str,
    payload: ArticleStatusUpdate,
    session: SessionDependency,
    embedding_client: EmbeddingClientDependency,
) -> KnowledgeArticleRead:
    workspace = await require_workspace(workspace_slug, session)
    article = await require_article(workspace.id, article_id, session)
    repository = KnowledgeArticleRepository(session)
    embedding: list[float] | None = None
    try:
        if payload.status == ArticleStatus.PUBLISHED:
            embedding = await embedding_client.embed(article_embedding_text(article))
        updated = await KnowledgeArticleService(repository).update_status(article, payload.status)
    except InvalidArticleTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    if updated.status == ArticleStatus.PUBLISHED and embedding is not None:
        await repository.upsert_embedding(
            article=updated, model=embedding_client.model_name, embedding=embedding
        )
    elif updated.status != ArticleStatus.PUBLISHED:
        await repository.delete_embedding(updated)
    return updated
