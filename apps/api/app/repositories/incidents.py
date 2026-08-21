from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident, IncidentStatus


class IncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, incident: Incident) -> Incident:
        self.session.add(incident)
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def get_by_incident_id(self, incident_id: str) -> Incident | None:
        result = await self.session.execute(
            select(Incident).where(Incident.incident_id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self, *, status: IncidentStatus | None, limit: int, offset: int
    ) -> list[Incident]:
        statement = select(Incident).order_by(Incident.created_at.desc())
        if status is not None:
            statement = statement.where(Incident.status == status)
        result = await self.session.execute(statement.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def set_status(self, incident: Incident, status: IncidentStatus) -> Incident:
        incident.status = status
        await self.session.commit()
        await self.session.refresh(incident)
        return incident
