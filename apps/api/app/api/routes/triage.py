from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.support import require_ticket, require_workspace
from app.db.session import get_session
from app.repositories.triage import TicketTriageRepository
from app.schemas.triage import TicketTriageRead
from app.services.embeddings import ChatClient, get_triage_chat_client
from app.services.triage import TicketTriageService, TicketTriageSpecialist

router = APIRouter(prefix="/workspaces/{workspace_slug}/tickets/{ticket_id}/triage", tags=["ticket triage"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
ChatClientDependency = Annotated[ChatClient, Depends(get_triage_chat_client)]


@router.post("", response_model=TicketTriageRead)
async def assess_ticket(
    workspace_slug: str,
    ticket_id: str,
    session: SessionDependency,
    chat_client: ChatClientDependency,
) -> TicketTriageRead:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    return await TicketTriageService(
        TicketTriageRepository(session), TicketTriageSpecialist(chat_client)
    ).assess(ticket)


@router.get("", response_model=TicketTriageRead | None)
async def get_latest_assessment(
    workspace_slug: str, ticket_id: str, session: SessionDependency
) -> TicketTriageRead | None:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    return await TicketTriageRepository(session).latest_for_ticket(ticket.id)
