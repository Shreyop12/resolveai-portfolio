import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter

from app.models.draft_evaluation import (
    DraftEvaluationCase,
    DraftEvaluationRun,
    DraftEvaluationRunStatus,
)
from app.models.knowledge import KnowledgeArticle
from app.models.ticket import SupportTicket, TicketPriority
from app.models.grounding_review import GroundingReviewDecision
from app.repositories.draft_evaluations import DraftEvaluationRepository
from app.schemas.draft_evaluations import DraftModelQualityMetric, DraftModelQualityReport
from app.services.draft_coordinator import GroundedDraftWriter
from app.services.embeddings import ChatClient, EmbeddingProviderError
from app.services.grounding_reviewer import GroundingReviewer
from app.services.draft_quality import DraftQualityChecker
from app.core.config import get_settings
from app.schemas.draft_evaluations import ConfiguredDraftModel


@dataclass
class DraftGenerationAttempt:
    """The independent writer stage, kept separate from the shared local reviewer."""

    provider: str
    model: str
    body: str | None
    draft_generation_latency_ms: int
    error_message: str | None = None
    provider_attempts: list[dict[str, str | int | None]] = field(default_factory=list)


class DraftModelComparisonService:
    """Runs isolated synthetic comparisons; it never calls the customer-ticket coordinator."""

    def __init__(
        self,
        repository: DraftEvaluationRepository,
        ollama_writer_client: ChatClient,
        openrouter_writer_client: ChatClient,
        reviewer: GroundingReviewer,
    ) -> None:
        self.repository = repository
        self.ollama_writer_client = ollama_writer_client
        self.openrouter_writer_client = openrouter_writer_client
        self.reviewer = reviewer

    async def compare(
        self, case: DraftEvaluationCase, article: KnowledgeArticle
    ) -> list[DraftEvaluationRun]:
        ticket = SupportTicket(
            ticket_id=f"SYNTHETIC-{case.evaluation_id}",
            workspace_id=case.workspace_id,
            customer_name="Evaluation Customer",
            customer_email="evaluation@example.invalid",
            subject=case.subject,
            message=case.message,
            priority=TicketPriority.NORMAL,
        )
        sources = [(article.article_id, article.title, article.body)]
        attempts = await asyncio.gather(
            self._write_draft(ticket, sources, "ollama", self.ollama_writer_client),
            self._write_draft(ticket, sources, "openrouter", self.openrouter_writer_client),
        )
        # Both reviews use the same local GPU-backed reviewer. Serializing them avoids
        # VRAM contention while keeping the two network/model writer calls concurrent.
        return [
            await self._review_and_save(case, ticket, sources, attempt)
            for attempt in attempts
        ]

    async def _write_draft(
        self,
        ticket: SupportTicket,
        sources: list[tuple[str, str, str]],
        provider: str,
        client: ChatClient,
    ) -> DraftGenerationAttempt:
        started_at = perf_counter()
        try:
            body = await GroundedDraftWriter(client).write(ticket, sources)
            return DraftGenerationAttempt(
                provider=provider,
                model=client.model_name,
                body=body,
                draft_generation_latency_ms=round((perf_counter() - started_at) * 1000),
                provider_attempts=list(getattr(client, "last_attempts", [])),
            )
        except EmbeddingProviderError as error:
            return DraftGenerationAttempt(
                provider=provider,
                model=client.model_name,
                body=None,
                draft_generation_latency_ms=round((perf_counter() - started_at) * 1000),
                error_message=str(error)[:500],
                provider_attempts=list(getattr(client, "last_attempts", [])),
            )

    async def _review_and_save(
        self,
        case: DraftEvaluationCase,
        ticket: SupportTicket,
        sources: list[tuple[str, str, str]],
        attempt: DraftGenerationAttempt,
    ) -> DraftEvaluationRun:
        if attempt.error_message is not None:
            return await self.repository.create_run(
                DraftEvaluationRun(
                    run_id=f"CMP-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
                    case_id=case.id,
                    provider=attempt.provider,
                    model=attempt.model,
                    status=DraftEvaluationRunStatus.FAILED,
                    error_message=attempt.error_message,
                    latency_ms=attempt.draft_generation_latency_ms,
                    draft_generation_latency_ms=attempt.draft_generation_latency_ms,
                    provider_attempts=attempt.provider_attempts,
                )
            )

        quality = DraftQualityChecker.assess(ticket, attempt.body or "")
        review_started_at = perf_counter()
        try:
            review = await self.reviewer.review(ticket, attempt.body or "", sources)
            review_latency_ms = round((perf_counter() - review_started_at) * 1000)
            run = DraftEvaluationRun(
                run_id=f"CMP-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
                case_id=case.id,
                provider=attempt.provider,
                model=attempt.model,
                status=DraftEvaluationRunStatus.COMPLETED,
                draft_body=attempt.body,
                review_decision=review.decision,
                review_reason=review.reason[:500],
                latency_ms=attempt.draft_generation_latency_ms + review_latency_ms,
                draft_generation_latency_ms=attempt.draft_generation_latency_ms,
                grounding_review_latency_ms=review_latency_ms,
                provider_attempts=attempt.provider_attempts,
                quality_decision=quality.decision,
                quality_reason=quality.reason,
            )
        except EmbeddingProviderError as error:
            review_latency_ms = round((perf_counter() - review_started_at) * 1000)
            run = DraftEvaluationRun(
                run_id=f"CMP-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
                case_id=case.id,
                provider=attempt.provider,
                model=attempt.model,
                status=DraftEvaluationRunStatus.FAILED,
                error_message=str(error)[:500],
                latency_ms=attempt.draft_generation_latency_ms + review_latency_ms,
                draft_generation_latency_ms=attempt.draft_generation_latency_ms,
                grounding_review_latency_ms=review_latency_ms,
                provider_attempts=attempt.provider_attempts,
                quality_decision=quality.decision,
                quality_reason=quality.reason,
            )
        return await self.repository.create_run(run)


class DraftModelQualityService:
    """Turns isolated synthetic runs into transparent, human-readable model metrics."""

    @staticmethod
    def configured_models() -> list[ConfiguredDraftModel]:
        settings = get_settings()
        configured = [
            ConfiguredDraftModel(
                provider="ollama", model=settings.ollama_chat_model, role="local baseline"
            ),
            ConfiguredDraftModel(
                provider="openrouter",
                model=settings.openrouter_draft_model,
                role="hosted primary",
            ),
        ]
        if settings.openrouter_fallback_draft_model:
            configured.append(
                ConfiguredDraftModel(
                    provider="openrouter",
                    model=settings.openrouter_fallback_draft_model,
                    role="hosted fallback",
                )
            )
        return configured

    @staticmethod
    def summarize(
        runs: list[DraftEvaluationRun],
        active_models: list[ConfiguredDraftModel] | None = None,
    ) -> DraftModelQualityReport:
        grouped: dict[tuple[str, str], list[DraftEvaluationRun]] = defaultdict(list)
        for run in runs:
            grouped[(run.provider, run.model)].append(run)

        configured = active_models or DraftModelQualityService.configured_models()
        configured_by_key = {(item.provider, item.model): item for item in configured}

        models: list[DraftModelQualityMetric] = []
        for provider, model in sorted(set(grouped) | set(configured_by_key)):
            model_runs = grouped.get((provider, model), [])
            configured_model = configured_by_key.get((provider, model))
            completed_runs = [
                run for run in model_runs if run.status == DraftEvaluationRunStatus.COMPLETED
            ]
            grounded_runs = [
                run
                for run in completed_runs
                if run.review_decision == GroundingReviewDecision.GROUNDED
            ]
            scored_runs = [run for run in model_runs if run.human_score is not None]
            models.append(
                DraftModelQualityMetric(
                    provider=provider,
                    model=model,
                    is_active=configured_model is not None,
                    active_role=configured_model.role if configured_model else None,
                    total_runs=len(model_runs),
                    completed_runs=len(completed_runs),
                    failed_runs=sum(
                        run.status == DraftEvaluationRunStatus.FAILED for run in model_runs
                    ),
                    grounding_pass_rate=(
                        round(len(grounded_runs) / len(completed_runs), 3)
                        if completed_runs
                        else None
                    ),
                    human_scored_runs=len(scored_runs),
                    average_human_score=(
                        round(sum(run.human_score for run in scored_runs) / len(scored_runs), 2)
                        if scored_runs
                        else None
                    ),
                    average_latency_ms=round(
                        sum(run.latency_ms for run in model_runs) / len(model_runs)
                    )
                    if model_runs
                    else None,
                )
            )
        return DraftModelQualityReport(
            total_runs=len(runs), models=models, active_models=configured
        )
