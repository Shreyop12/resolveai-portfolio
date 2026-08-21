import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.triage import TicketTriageAssessment


class TicketTriageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, assessment: TicketTriageAssessment) -> TicketTriageAssessment:
        self.session.add(assessment)
        await self.session.commit()
        await self.session.refresh(assessment)
        return assessment

    async def latest_for_ticket(self, ticket_id: uuid.UUID) -> TicketTriageAssessment | None:
        result = await self.session.execute(
            select(TicketTriageAssessment)
            .where(TicketTriageAssessment.ticket_id == ticket_id)
            .order_by(TicketTriageAssessment.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
