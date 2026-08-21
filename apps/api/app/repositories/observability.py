import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observability import CoordinatorRun, RetrievalEvaluationCase


class CoordinatorRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, run: CoordinatorRun) -> CoordinatorRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def list_for_ticket(self, ticket_id: uuid.UUID) -> list[CoordinatorRun]:
        result = await self.session.execute(
            select(CoordinatorRun)
            .where(CoordinatorRun.ticket_id == ticket_id)
            .order_by(CoordinatorRun.created_at.desc())
        )
        return list(result.scalars().all())


class RetrievalEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, case: RetrievalEvaluationCase) -> RetrievalEvaluationCase:
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[RetrievalEvaluationCase]:
        result = await self.session.execute(
            select(RetrievalEvaluationCase)
            .where(RetrievalEvaluationCase.workspace_id == workspace_id)
            .order_by(RetrievalEvaluationCase.created_at.desc())
        )
        return list(result.scalars().all())
