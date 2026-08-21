from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import SupportTicket, TicketNote, TicketStatus
from app.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, workspace: Workspace) -> Workspace:
        self.session.add(workspace)
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def get_by_slug(self, slug: str) -> Workspace | None:
        result = await self.session.execute(select(Workspace).where(Workspace.slug == slug))
        return result.scalar_one_or_none()

    async def list(self) -> list[Workspace]:
        result = await self.session.execute(select(Workspace).order_by(Workspace.name))
        return list(result.scalars().all())


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, ticket: SupportTicket) -> SupportTicket:
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def list(
        self,
        *,
        workspace_id: object,
        status: TicketStatus | None,
        limit: int,
        offset: int,
    ) -> list[SupportTicket]:
        statement = (
            select(SupportTicket)
            .where(SupportTicket.workspace_id == workspace_id)
            .order_by(SupportTicket.created_at.desc())
        )
        if status is not None:
            statement = statement.where(SupportTicket.status == status)
        result = await self.session.execute(statement.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def get_by_ticket_id(
        self, *, workspace_id: object, ticket_id: str
    ) -> SupportTicket | None:
        statement = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.notes))
            .where(
                SupportTicket.workspace_id == workspace_id,
                SupportTicket.ticket_id == ticket_id,
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def set_status(self, ticket: SupportTicket, status: TicketStatus) -> SupportTicket:
        ticket.status = status
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def add_note(self, note: TicketNote) -> TicketNote:
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        return note
