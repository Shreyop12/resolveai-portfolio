import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_selection import ModelSelectionPolicy


class ModelSelectionPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, workspace_id: uuid.UUID) -> ModelSelectionPolicy | None:
        result = await self.session.execute(select(ModelSelectionPolicy).where(ModelSelectionPolicy.workspace_id == workspace_id))
        return result.scalar_one_or_none()

    async def save(self, policy: ModelSelectionPolicy) -> ModelSelectionPolicy:
        self.session.add(policy)
        await self.session.commit()
        await self.session.refresh(policy)
        return policy
