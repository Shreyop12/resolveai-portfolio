import uuid
from datetime import UTC, datetime

from app.models.ticket import SupportTicket, TicketNote, TicketStatus
from app.models.workspace import Workspace
from app.repositories.support import TicketRepository, WorkspaceRepository
from app.schemas.support import TicketCreate, TicketNoteCreate, WorkspaceCreate


class DuplicateWorkspaceSlugError(ValueError):
    """Raised when a workspace URL slug is already taken."""


class InvalidTicketTransitionError(ValueError):
    """Raised when a support ticket lifecycle transition is disallowed."""


ALLOWED_TICKET_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.DRAFTING, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.DRAFTING: {TicketStatus.OPEN, TicketStatus.AWAITING_REVIEW},
    TicketStatus.AWAITING_REVIEW: {
        TicketStatus.OPEN,
        TicketStatus.DRAFTING,
        TicketStatus.RESOLVED,
    },
    TicketStatus.RESOLVED: {TicketStatus.OPEN, TicketStatus.CLOSED},
    TicketStatus.CLOSED: {TicketStatus.OPEN},
}


class SupportWorkspaceService:
    def __init__(self, workspace_repository: WorkspaceRepository) -> None:
        self.workspace_repository = workspace_repository

    async def create_workspace(self, payload: WorkspaceCreate) -> Workspace:
        if await self.workspace_repository.get_by_slug(payload.slug):
            raise DuplicateWorkspaceSlugError(f"Workspace slug '{payload.slug}' is already in use.")
        return await self.workspace_repository.create(
            Workspace(name=payload.name, slug=payload.slug)
        )


class TicketService:
    def __init__(self, ticket_repository: TicketRepository) -> None:
        self.ticket_repository = ticket_repository

    async def create_ticket(self, workspace: Workspace, payload: TicketCreate) -> SupportTicket:
        year = datetime.now(UTC).year
        ticket = SupportTicket(
            ticket_id=f"TKT-{year}-{uuid.uuid4().hex[:8].upper()}",
            workspace_id=workspace.id,
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            subject=payload.subject,
            message=payload.message,
            priority=payload.priority,
            status=TicketStatus.OPEN,
        )
        return await self.ticket_repository.create(ticket)

    async def update_status(
        self, ticket: SupportTicket, status: TicketStatus
    ) -> SupportTicket:
        if status == ticket.status:
            return ticket
        if status not in ALLOWED_TICKET_TRANSITIONS[ticket.status]:
            raise InvalidTicketTransitionError(
                f"Cannot transition {ticket.status} to {status}."
            )
        return await self.ticket_repository.set_status(ticket, status)

    async def add_note(self, ticket: SupportTicket, payload: TicketNoteCreate) -> TicketNote:
        return await self.ticket_repository.add_note(
            TicketNote(ticket_id=ticket.id, body=payload.body, author=payload.author)
        )
