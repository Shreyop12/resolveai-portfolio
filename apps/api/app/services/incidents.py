import uuid
from datetime import UTC, datetime

from app.models.incident import Incident, IncidentStatus
from app.repositories.incidents import IncidentRepository
from app.schemas.incident import IncidentCreate


class InvalidStatusTransitionError(ValueError):
    """Raised when an incident lifecycle transition is disallowed."""


ALLOWED_STATUS_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.NEW: {IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED},
    IncidentStatus.INVESTIGATING: {
        IncidentStatus.AWAITING_APPROVAL,
        IncidentStatus.RESOLVED,
        IncidentStatus.CLOSED,
    },
    IncidentStatus.AWAITING_APPROVAL: {
        IncidentStatus.INVESTIGATING,
        IncidentStatus.RESOLVED,
    },
    IncidentStatus.RESOLVED: {IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: set(),
}


class IncidentService:
    def __init__(self, repository: IncidentRepository) -> None:
        self.repository = repository

    async def create(self, payload: IncidentCreate) -> Incident:
        year = datetime.now(UTC).year
        incident = Incident(
            incident_id=f"INC-{year}-{uuid.uuid4().hex[:8].upper()}",
            title=payload.title,
            description=payload.description,
            severity=payload.severity,
            status=IncidentStatus.NEW,
        )
        return await self.repository.create(incident)

    async def update_status(self, incident: Incident, status: IncidentStatus) -> Incident:
        if status == incident.status:
            return incident
        if status not in ALLOWED_STATUS_TRANSITIONS[incident.status]:
            raise InvalidStatusTransitionError(
                f"Cannot transition {incident.status} to {status}."
            )
        return await self.repository.set_status(incident, status)
