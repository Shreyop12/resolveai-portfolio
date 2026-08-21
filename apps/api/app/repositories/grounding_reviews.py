import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grounding_review import TicketGroundingReview


class TicketGroundingReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, review: TicketGroundingReview) -> TicketGroundingReview:
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def attach_draft(
        self, review: TicketGroundingReview, draft_id: uuid.UUID
    ) -> TicketGroundingReview:
        review.draft_id = draft_id
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def latest_for_ticket(self, ticket_id: uuid.UUID) -> TicketGroundingReview | None:
        result = await self.session.execute(
            select(TicketGroundingReview)
            .where(TicketGroundingReview.ticket_id == ticket_id)
            .order_by(TicketGroundingReview.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
