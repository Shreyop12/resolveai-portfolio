from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.support import require_ticket, require_workspace
from app.db.session import get_session
from app.models.draft import DraftReviewStatus
from app.models.ticket import TicketStatus
from app.repositories.drafts import TicketDraftRepository
from app.repositories.grounding_reviews import TicketGroundingReviewRepository
from app.repositories.knowledge import KnowledgeArticleRepository
from app.repositories.observability import CoordinatorRunRepository
from app.repositories.support import TicketRepository
from app.repositories.triage import TicketTriageRepository
from app.schemas.drafts import TicketDraftRead, TicketDraftReview
from app.schemas.grounding_reviews import TicketGroundingReviewRead
from app.schemas.observability import CoordinatorRunRead
from app.services.draft_coordinator import (
    CannotDraftForTicketError,
    GroundedDraftWriter,
    GroundingReviewRequiredError,
    NoApprovedSourcesError,
    SupportDraftCoordinator,
    TriageRequiredError,
)
from app.services.grounding_reviewer import GroundingReviewer
from app.services.embeddings import (
    ChatClient,
    EmbeddingClient,
    EmbeddingProviderError,
    get_draft_chat_client,
    get_embedding_client,
    get_reviewer_chat_client,
)
from app.services.support import InvalidTicketTransitionError, TicketService

router = APIRouter(prefix="/workspaces/{workspace_slug}/tickets/{ticket_id}/drafts", tags=["draft coordinator"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
EmbeddingClientDependency = Annotated[EmbeddingClient, Depends(get_embedding_client)]
DraftChatClientDependency = Annotated[ChatClient, Depends(get_draft_chat_client)]
ReviewerChatClientDependency = Annotated[ChatClient, Depends(get_reviewer_chat_client)]


@router.post("/generate", response_model=TicketDraftRead, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    workspace_slug: str,
    ticket_id: str,
    session: SessionDependency,
    embedding_client: EmbeddingClientDependency,
    draft_chat_client: DraftChatClientDependency,
    reviewer_chat_client: ReviewerChatClientDependency,
) -> TicketDraftRead:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    coordinator = SupportDraftCoordinator(
        ticket_repository=TicketRepository(session),
        knowledge_repository=KnowledgeArticleRepository(session),
        draft_repository=TicketDraftRepository(session),
        run_repository=CoordinatorRunRepository(session),
        triage_repository=TicketTriageRepository(session),
        grounding_review_repository=TicketGroundingReviewRepository(session),
        embedding_client=embedding_client,
        writer=GroundedDraftWriter(draft_chat_client),
        reviewer=GroundingReviewer(reviewer_chat_client),
    )
    try:
        return await coordinator.generate(ticket)
    except (
        NoApprovedSourcesError,
        CannotDraftForTicketError,
        TriageRequiredError,
        GroundingReviewRequiredError,
    ) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("", response_model=list[TicketDraftRead])
async def list_drafts(
    workspace_slug: str, ticket_id: str, session: SessionDependency
) -> list[TicketDraftRead]:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    return await TicketDraftRepository(session).list_for_ticket(ticket.id)


@router.get("/runs", response_model=list[CoordinatorRunRead])
async def list_coordinator_runs(
    workspace_slug: str, ticket_id: str, session: SessionDependency
) -> list[CoordinatorRunRead]:
    """Expose safe run metadata, never prompts or model reasoning."""
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    return await CoordinatorRunRepository(session).list_for_ticket(ticket.id)


@router.get("/grounding-review", response_model=TicketGroundingReviewRead | None)
async def get_latest_grounding_review(
    workspace_slug: str, ticket_id: str, session: SessionDependency
) -> TicketGroundingReviewRead | None:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    return await TicketGroundingReviewRepository(session).latest_for_ticket(ticket.id)


@router.patch("/{draft_id}/review", response_model=TicketDraftRead)
async def review_draft(
    workspace_slug: str,
    ticket_id: str,
    draft_id: str,
    payload: TicketDraftReview,
    session: SessionDependency,
) -> TicketDraftRead:
    if payload.status not in {DraftReviewStatus.APPROVED, DraftReviewStatus.REJECTED}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose approved or rejected.")
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    repository = TicketDraftRepository(session)
    draft = await repository.get_by_draft_id(ticket.id, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    if draft.status != DraftReviewStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This draft has already been reviewed.")
    try:
        await TicketService(TicketRepository(session)).update_status(
            ticket,
            TicketStatus.RESOLVED if payload.status == DraftReviewStatus.APPROVED else TicketStatus.DRAFTING,
        )
    except InvalidTicketTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return await repository.review(draft, payload.status)
