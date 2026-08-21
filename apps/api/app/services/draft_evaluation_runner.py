"""Durable execution of one synthetic draft-evaluation job."""

import logging

from app.db.session import SessionLocal
from app.models.draft_evaluation import DraftEvaluationJob
from app.models.knowledge import ArticleStatus
from app.repositories.draft_evaluations import DraftEvaluationRepository
from app.repositories.knowledge import KnowledgeArticleRepository
from app.services.draft_evaluation import DraftModelComparisonService
from app.services.embeddings import (
    ChatClient,
    GeminiChatClient,
    OpenRouterChatClient,
    get_ollama_draft_chat_client,
    get_openrouter_draft_chat_client,
    get_reviewer_chat_client,
)
from app.core.config import get_settings
from app.services.grounding_reviewer import GroundingReviewer

logger = logging.getLogger(__name__)


async def process_draft_evaluation_job(job_id: str) -> None:
    """Claim, execute, and durably finish one job from any execution environment."""
    async with SessionLocal() as session:
        repository = DraftEvaluationRepository(session)
        job = await repository.claim_job(job_id)
        await _process_claimed_job(repository, job)


async def process_next_draft_evaluation_job() -> bool:
    """Claim and execute one database-queued job; return whether work was found."""
    async with SessionLocal() as session:
        repository = DraftEvaluationRepository(session)
        job = await repository.claim_next_queued_job()
        if job is None:
            return False
        await _process_claimed_job(repository, job)
        return True


async def _process_claimed_job(
    repository: DraftEvaluationRepository, job: DraftEvaluationJob | None
) -> None:
    if job is None:
        return
    try:
        case = await repository.get_case_by_id(job.case_id)
        if case is None:
            raise ValueError("The draft evaluation case no longer exists.")
        article = await KnowledgeArticleRepository(repository.session).get_by_article_id(
            workspace_id=case.workspace_id, article_id=case.expected_article_id
        )
        if article is None or article.status != ArticleStatus.PUBLISHED:
            raise ValueError("The expected evaluation source must remain published.")
        first_writer, second_writer, first_provider, second_provider = _get_evaluation_writer_clients()
        comparison = DraftModelComparisonService(
            repository,
            first_writer,
            second_writer,
            GroundingReviewer(get_reviewer_chat_client()),
            first_provider,
            second_provider,
        )
        await comparison.compare(case, article)
        await repository.complete_job(job)
    except Exception as error:
        logger.exception("Draft evaluation job %s failed.", job.job_id)
        await repository.fail_job(job, str(error) or "The worker stopped unexpectedly.")


def _get_evaluation_writer_clients() -> tuple[ChatClient, ChatClient, str, str]:
    """Keep local comparisons local, while cloud comparisons never call laptop Ollama."""
    settings = get_settings()
    if settings.agent_provider == "gemini":
        return (
            GeminiChatClient(model_name=settings.gemini_model),
            OpenRouterChatClient(
                model_name=settings.openrouter_draft_model,
                use_configured_fallback=False,
            ),
            "gemini-primary",
            "openrouter-fallback",
        )
    if settings.agent_provider == "openrouter":
        fallback_model = settings.openrouter_fallback_draft_model
        if not fallback_model:
            raise ValueError(
                "Cloud model comparisons require RESOLVEAI_OPENROUTER_FALLBACK_DRAFT_MODEL."
            )
        return (
            OpenRouterChatClient(
                model_name=settings.openrouter_draft_model,
                use_configured_fallback=False,
            ),
            OpenRouterChatClient(model_name=fallback_model, use_configured_fallback=False),
            "openrouter-primary",
            "openrouter-fallback",
        )
    return (
        get_ollama_draft_chat_client(),
        get_openrouter_draft_chat_client(),
        "ollama",
        "openrouter",
    )
