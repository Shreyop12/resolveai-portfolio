import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.support import require_workspace
from app.db.session import get_session
from app.models.knowledge import ArticleStatus
from app.models.observability import RetrievalEvaluationCase
from app.repositories.knowledge import KnowledgeArticleRepository
from app.repositories.observability import RetrievalEvaluationRepository
from app.schemas.observability import (
    RetrievalEvaluationCaseRead,
    RetrievalEvaluationCreate,
    RetrievalEvaluationReport,
    RetrievalEvaluationResult,
)
from app.services.embeddings import (
    EmbeddingClient,
    EmbeddingProviderError,
    get_embedding_client,
)
from app.services.retrieval_evaluation import HybridRetrievalEvaluator

router = APIRouter(
    prefix="/workspaces/{workspace_slug}/retrieval-evaluations", tags=["retrieval evaluation"]
)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
EmbeddingClientDependency = Annotated[EmbeddingClient, Depends(get_embedding_client)]


@router.post("", response_model=RetrievalEvaluationCaseRead, status_code=status.HTTP_201_CREATED)
async def create_evaluation_case(
    workspace_slug: str, payload: RetrievalEvaluationCreate, session: SessionDependency
) -> RetrievalEvaluationCaseRead:
    workspace = await require_workspace(workspace_slug, session)
    article = await KnowledgeArticleRepository(session).get_by_article_id(
        workspace_id=workspace.id, article_id=payload.expected_article_id
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expected knowledge article not found.")
    if article.status != ArticleStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An evaluation case must expect a published knowledge article.",
        )
    year = datetime.now(UTC).year
    return await RetrievalEvaluationRepository(session).create(
        RetrievalEvaluationCase(
            evaluation_id=f"EVAL-{year}-{uuid.uuid4().hex[:8].upper()}",
            workspace_id=workspace.id,
            query=payload.query,
            expected_article_id=payload.expected_article_id,
        )
    )


@router.get("", response_model=list[RetrievalEvaluationCaseRead])
async def list_evaluation_cases(
    workspace_slug: str, session: SessionDependency
) -> list[RetrievalEvaluationCaseRead]:
    workspace = await require_workspace(workspace_slug, session)
    return await RetrievalEvaluationRepository(session).list_for_workspace(workspace.id)


@router.post("/run", response_model=RetrievalEvaluationReport)
async def run_evaluation(
    workspace_slug: str,
    session: SessionDependency,
    embedding_client: EmbeddingClientDependency,
) -> RetrievalEvaluationReport:
    """Run each human-labelled question through the same hybrid retrieval used by the coordinator."""
    workspace = await require_workspace(workspace_slug, session)
    cases = await RetrievalEvaluationRepository(session).list_for_workspace(workspace.id)
    try:
        outcomes = await HybridRetrievalEvaluator(
            KnowledgeArticleRepository(session), embedding_client
        ).evaluate(workspace_id=workspace.id, cases=cases, limit=5)
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    total = len(outcomes)
    results = [
        RetrievalEvaluationResult(
            evaluation_id=outcome.case.evaluation_id,
            expected_article_id=outcome.case.expected_article_id,
            retrieved_article_ids=outcome.retrieved_article_ids,
            expected_rank=outcome.expected_rank,
            hit_at_k=outcome.expected_rank is not None,
            reciprocal_rank=outcome.reciprocal_rank,
        )
        for outcome in outcomes
    ]
    return RetrievalEvaluationReport(
        total_cases=total,
        hit_at_k=sum(result.hit_at_k for result in results) / total if total else 0.0,
        mean_reciprocal_rank=sum(result.reciprocal_rank for result in results) / total if total else 0.0,
        results=results,
    )
