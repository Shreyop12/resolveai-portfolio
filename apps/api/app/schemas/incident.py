import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import IncidentSeverity, IncidentStatus


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=20_000)
    severity: IncidentSeverity = IncidentSeverity.MEDIUM


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: str
    title: str
    description: str
    status: IncidentStatus
    severity: IncidentSeverity
    created_at: datetime
    updated_at: datetime


class IncidentList(BaseModel):
    items: list[IncidentRead]
    limit: int
    offset: int
