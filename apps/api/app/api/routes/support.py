from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.ticket import TicketStatus
from app.repositories.support import TicketRepository, WorkspaceRepository
from app.schemas.support import (
    TicketCreate,
    TicketDetailRead,
    TicketList,
    TicketNoteCreate,
    TicketNoteRead,
    TicketRead,
    TicketStatusUpdate,
    WorkspaceCreate,
    WorkspaceRead,
)
from app.services.support import (
    DuplicateWorkspaceSlugError,
    InvalidTicketTransitionError,
    SupportWorkspaceService,
    TicketService,
)

router = APIRouter(tags=["support workspace"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def require_workspace(slug: str, session: AsyncSession):
    workspace = await WorkspaceRepository(session).get_by_slug(slug)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


async def require_ticket(workspace_id: object, ticket_id: str, session: AsyncSession):
    ticket = await TicketRepository(session).get_by_ticket_id(
        workspace_id=workspace_id, ticket_id=ticket_id
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return ticket


@router.post("/workspaces", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreate, session: SessionDependency) -> WorkspaceRead:
    try:
        return await SupportWorkspaceService(WorkspaceRepository(session)).create_workspace(payload)
    except DuplicateWorkspaceSlugError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/workspaces", response_model=list[WorkspaceRead])
async def list_workspaces(session: SessionDependency) -> list[WorkspaceRead]:
    return await WorkspaceRepository(session).list()


@router.post(
    "/workspaces/{workspace_slug}/tickets",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    workspace_slug: str, payload: TicketCreate, session: SessionDependency
) -> TicketRead:
    workspace = await require_workspace(workspace_slug, session)
    return await TicketService(TicketRepository(session)).create_ticket(workspace, payload)


@router.get("/workspaces/{workspace_slug}/tickets", response_model=TicketList)
async def list_tickets(
    workspace_slug: str,
    session: SessionDependency,
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketList:
    workspace = await require_workspace(workspace_slug, session)
    tickets = await TicketRepository(session).list(
        workspace_id=workspace.id, status=status_filter, limit=limit, offset=offset
    )
    return TicketList(items=tickets, limit=limit, offset=offset)


@router.get(
    "/workspaces/{workspace_slug}/tickets/{ticket_id}", response_model=TicketDetailRead
)
async def get_ticket(
    workspace_slug: str, ticket_id: str, session: SessionDependency
) -> TicketDetailRead:
    workspace = await require_workspace(workspace_slug, session)
    return await require_ticket(workspace.id, ticket_id, session)


@router.patch(
    "/workspaces/{workspace_slug}/tickets/{ticket_id}/status", response_model=TicketRead
)
async def update_ticket_status(
    workspace_slug: str,
    ticket_id: str,
    payload: TicketStatusUpdate,
    session: SessionDependency,
) -> TicketRead:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    try:
        return await TicketService(TicketRepository(session)).update_status(ticket, payload.status)
    except InvalidTicketTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/workspaces/{workspace_slug}/tickets/{ticket_id}/notes",
    response_model=TicketNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_ticket_note(
    workspace_slug: str,
    ticket_id: str,
    payload: TicketNoteCreate,
    session: SessionDependency,
) -> TicketNoteRead:
    workspace = await require_workspace(workspace_slug, session)
    ticket = await require_ticket(workspace.id, ticket_id, session)
    return await TicketService(TicketRepository(session)).add_note(ticket, payload)
