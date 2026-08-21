import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft import DraftReviewStatus, TicketDraft


class TicketDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, draft: TicketDraft) -> TicketDraft:
        self.session.add(draft)
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    async def list_for_ticket(self, ticket_id: uuid.UUID) -> list[TicketDraft]:
        result = await self.session.execute(
            select(TicketDraft)
            .where(TicketDraft.ticket_id == ticket_id)
            .order_by(TicketDraft.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_draft_id(self, ticket_id: uuid.UUID, draft_id: str) -> TicketDraft | None:
        result = await self.session.execute(
            select(TicketDraft).where(
                TicketDraft.ticket_id == ticket_id, TicketDraft.draft_id == draft_id
            )
        )
        return result.scalar_one_or_none()

    async def review(self, draft: TicketDraft, status: DraftReviewStatus) -> TicketDraft:
        draft.status = status
        draft.reviewed_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(draft)
        return draft
