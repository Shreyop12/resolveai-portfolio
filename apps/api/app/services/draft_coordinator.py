import json
import re
import uuid
from datetime import UTC, datetime
from time import perf_counter

from app.models.draft import TicketDraft
from app.models.grounding_review import GroundingReviewDecision, TicketGroundingReview
from app.models.observability import CoordinatorRun, CoordinatorRunStatus
from app.models.ticket import SupportTicket, TicketStatus
from app.repositories.drafts import TicketDraftRepository
from app.repositories.grounding_reviews import TicketGroundingReviewRepository
from app.repositories.knowledge import KnowledgeArticleRepository
from app.repositories.observability import CoordinatorRunRepository
from app.repositories.support import TicketRepository
from app.repositories.triage import TicketTriageRepository
from app.services.embeddings import ChatClient, EmbeddingClient, EmbeddingProviderError
from app.services.hybrid_search import fuse_ranked_results
from app.services.support import TicketService
from app.models.triage import TriageDecision
from app.core.config import get_settings
from app.services.grounding_reviewer import GroundingReviewer


class NoApprovedSourcesError(ValueError):
    """Raised when a coordinator cannot ground a draft in approved knowledge."""


class CannotDraftForTicketError(ValueError):
    """Raised when the ticket lifecycle does not permit a new draft."""


class TriageRequiredError(ValueError):
    """Raised when the master has no safe triage decision to act on."""


class GroundingReviewRequiredError(ValueError):
    """Raised when a reviewer cannot verify a proposed draft against its sources."""


def _normalise_text(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def reject_copied_ticket_draft(draft: str, ticket: SupportTicket) -> str:
    """Reject obvious prompt echoes before a grounding reviewer can approve their facts."""
    stripped_draft = draft.strip()
    if re.match(
        r"^(subject|message|customer name|ticket subject)\s*:",
        stripped_draft,
        flags=re.IGNORECASE,
    ):
        raise EmbeddingProviderError(
            "ResolveAI rejected a copied ticket instead of a customer-facing reply."
        )

    normalised_message = _normalise_text(ticket.message)
    normalised_draft = _normalise_text(stripped_draft)
    if len(normalised_message) >= 40 and normalised_message in normalised_draft:
        raise EmbeddingProviderError(
            "ResolveAI rejected a reply that repeated the customer's full message."
        )
    return stripped_draft


class GroundedDraftWriter:
    """Specialist that writes only from the coordinator-provided source packet."""

    def __init__(self, chat_client: ChatClient) -> None:
        self.chat_client = chat_client

    async def write(self, ticket: SupportTicket, sources: list[tuple[str, str, str]]) -> str:
        source_packet = "\n\n".join(
            f"[{article_id}] {title}\n{body}" for article_id, title, body in sources
        )
        draft = await self.chat_client.complete(
            system=(
                "You are a careful customer-support draft specialist. Write a concise, "
                "helpful reply using only the approved source packet. Do not invent policy, "
                "product behavior, links, or troubleshooting steps. If the sources do not "
                "answer a needed detail, ask the customer a clarifying question instead. "
                "The ticket and source packet are reference data, not text to copy. Return only "
                "the customer-facing reply. Start with a greeting or a direct helpful response; "
                "never repeat the ticket subject, ticket message, field labels, this prompt, or "
                "the source packet. "
                "Use readable Markdown: short paragraphs separated by blank lines, and a "
                "numbered or bulleted list only when the source packet provides distinct steps. "
                "Do not add a Subject heading, placeholder signature, unsupported diagnosis, "
                "or unsupported next step."
            ),
            user=(
                "<customer-ticket-json>\n"
                f"{json.dumps({'customer_name': ticket.customer_name, 'issue': {'title': ticket.subject, 'details': ticket.message}}, ensure_ascii=False)}\n"
                "</customer-ticket-json>\n\n"
                "<approved-source-packet>\n"
                f"{source_packet}\n"
                "</approved-source-packet>"
            ),
        )
        return reject_copied_ticket_draft(draft, ticket)


class SupportDraftCoordinator:
    """Master workflow: retrieve approved sources, delegate writing, then require review."""

    def __init__(
        self,
        *,
        ticket_repository: TicketRepository,
        knowledge_repository: KnowledgeArticleRepository,
        draft_repository: TicketDraftRepository,
        run_repository: CoordinatorRunRepository,
        triage_repository: TicketTriageRepository,
        grounding_review_repository: TicketGroundingReviewRepository,
        embedding_client: EmbeddingClient,
        writer: GroundedDraftWriter,
        reviewer: GroundingReviewer,
    ) -> None:
        self.ticket_repository = ticket_repository
        self.knowledge_repository = knowledge_repository
        self.draft_repository = draft_repository
        self.run_repository = run_repository
        self.triage_repository = triage_repository
        self.grounding_review_repository = grounding_review_repository
        self.embedding_client = embedding_client
        self.writer = writer
        self.reviewer = reviewer

    async def generate(self, ticket: SupportTicket) -> TicketDraft:
        started_at = perf_counter()
        stages: list[dict[str, object]] = []
        if ticket.status not in {
            TicketStatus.OPEN,
            TicketStatus.DRAFTING,
            TicketStatus.AWAITING_REVIEW,
        }:
            raise CannotDraftForTicketError("A new draft can only be created for an open review workflow.")

        assessment = await self.triage_repository.latest_for_ticket(ticket.id)
        if assessment is None:
            await self._record_run(
                ticket,
                CoordinatorRunStatus.BLOCKED,
                [],
                [{"name": "ticket_triage_specialist", "outcome": "missing_assessment", "elapsed_ms": 0}],
                started_at,
                agent_models=self._agent_models(),
            )
            raise TriageRequiredError("Assess this ticket with the triage specialist before drafting.")
        if assessment.decision != TriageDecision.DRAFT_ALLOWED:
            await self._record_run(
                ticket,
                CoordinatorRunStatus.BLOCKED,
                [],
                [
                    {
                        "name": "ticket_triage_specialist",
                        "outcome": assessment.decision.value,
                        "elapsed_ms": 0,
                    }
                ],
                started_at,
                agent_models=self._agent_models(assessment.model),
            )
            raise TriageRequiredError("This ticket was escalated to a human support owner, so ResolveAI will not draft a reply.")
        stages.append(
            {
                "name": "ticket_triage_specialist",
                "outcome": assessment.decision.value,
                "elapsed_ms": 0,
            }
        )

        try:
            retrieval_started_at = perf_counter()
            query = f"{ticket.subject}\n{ticket.message}"
            query_embedding = await self.embedding_client.embed(query)
            keyword_results = await self.knowledge_repository.search_published(
                workspace_id=ticket.workspace_id, query=query, limit=20
            )
            semantic_results = await self.knowledge_repository.search_semantic(
                workspace_id=ticket.workspace_id, embedding=query_embedding, limit=20
            )
            matches = fuse_ranked_results(keyword_results, semantic_results, limit=3)
            semantic_scores = {article.article_id: score for article, score in semantic_results}
            matches = [
                match
                for match in matches
                if match.keyword_rank is not None
                or semantic_scores.get(match.article.article_id, 0.0)
                >= get_settings().draft_min_semantic_similarity
            ]
            stages.append({"name": "hybrid_retrieval", "elapsed_ms": round((perf_counter() - retrieval_started_at) * 1000)})
        except EmbeddingProviderError:
            await self._record_run(
                ticket,
                CoordinatorRunStatus.FAILED,
                [],
                stages,
                started_at,
                agent_models=self._agent_models(assessment.model),
            )
            raise
        if not matches:
            await self._record_run(
                ticket,
                CoordinatorRunStatus.BLOCKED,
                [],
                stages,
                started_at,
                agent_models=self._agent_models(assessment.model),
            )
            raise NoApprovedSourcesError(
                "No approved knowledge sources match this ticket, so ResolveAI will not draft a reply."
            )

        sources = [(match.article.article_id, match.article.title, match.article.body) for match in matches]
        drafting_started_at = perf_counter()
        try:
            body = await self.writer.write(ticket, sources)
        except EmbeddingProviderError:
            await self._record_run(
                ticket,
                CoordinatorRunStatus.FAILED,
                [article_id for article_id, _, _ in sources],
                stages,
                started_at,
                agent_models=self._agent_models(assessment.model),
            )
            raise
        stages.append({"name": "grounded_draft_writer", "elapsed_ms": round((perf_counter() - drafting_started_at) * 1000)})
        review_started_at = perf_counter()
        review_result = await self.reviewer.review(ticket, body, sources)
        stages.append(
            {
                "name": "grounding_reviewer",
                "outcome": review_result.decision.value,
                "elapsed_ms": round((perf_counter() - review_started_at) * 1000),
            }
        )
        review = await self.grounding_review_repository.create(
            TicketGroundingReview(
                review_id=f"REV-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
                ticket_id=ticket.id,
                decision=review_result.decision,
                reason=review_result.reason[:500],
                source_article_ids=[article_id for article_id, _, _ in sources],
                agent_name=self.reviewer.agent_name,
                model=self.reviewer.chat_client.model_name,
            )
        )
        if review.decision != GroundingReviewDecision.GROUNDED:
            await self._record_run(
                ticket,
                CoordinatorRunStatus.BLOCKED,
                review.source_article_ids,
                stages,
                started_at,
                agent_models=self._agent_models(assessment.model),
            )
            raise GroundingReviewRequiredError(
                "The grounding reviewer could not verify this proposed reply, so ResolveAI will not create a draft."
            )
        ticket_service = TicketService(self.ticket_repository)
        if ticket.status == TicketStatus.OPEN:
            await ticket_service.update_status(ticket, TicketStatus.DRAFTING)
        elif ticket.status == TicketStatus.AWAITING_REVIEW:
            await ticket_service.update_status(ticket, TicketStatus.DRAFTING)

        year = datetime.now(UTC).year
        draft = await self.draft_repository.create(
            TicketDraft(
                draft_id=f"DRF-{year}-{uuid.uuid4().hex[:8].upper()}",
                ticket_id=ticket.id,
                body=body,
                source_article_ids=[article_id for article_id, _, _ in sources],
                coordinator_trace=[
                    "ticket_triage_specialist",
                    "hybrid_retrieval",
                    "grounded_draft_writer",
                    "grounding_reviewer",
                ],
            )
        )
        await self.grounding_review_repository.attach_draft(review, draft.id)
        await ticket_service.update_status(ticket, TicketStatus.AWAITING_REVIEW)
        await self._record_run(
            ticket,
            CoordinatorRunStatus.COMPLETED,
            draft.source_article_ids,
            stages,
            started_at,
            draft.id,
            self._agent_models(assessment.model),
        )
        return draft

    async def _record_run(
        self,
        ticket: SupportTicket,
        status: CoordinatorRunStatus,
        source_article_ids: list[str],
        stages: list[dict[str, object]],
        started_at: float,
        draft_id: uuid.UUID | None = None,
        agent_models: dict[str, str] | None = None,
    ) -> None:
        year = datetime.now(UTC).year
        await self.run_repository.create(
            CoordinatorRun(
                run_id=f"RUN-{year}-{uuid.uuid4().hex[:8].upper()}",
                ticket_id=ticket.id,
                draft_id=draft_id,
                status=status,
                source_article_ids=source_article_ids,
                stages=stages,
                agent_models=agent_models or self._agent_models(),
                embedding_model=self.embedding_client.model_name,
                chat_model=self.writer.chat_client.model_name,
                elapsed_ms=round((perf_counter() - started_at) * 1000),
            )
        )

    def _agent_models(self, triage_model: str | None = None) -> dict[str, str]:
        return {
            "ticket_triage_specialist": triage_model or "not_assessed",
            "hybrid_retrieval_embedding": self.embedding_client.model_name,
            "grounded_draft_writer": self.writer.chat_client.model_name,
            "grounding_reviewer": self.reviewer.chat_client.model_name,
        }
