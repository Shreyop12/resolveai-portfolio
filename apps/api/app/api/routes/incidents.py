from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.incident import IncidentStatus
from app.repositories.incidents import IncidentRepository
from app.schemas.incident import IncidentCreate, IncidentList, IncidentRead, IncidentStatusUpdate
from app.services.incidents import IncidentService, InvalidStatusTransitionError

router = APIRouter(prefix="/incidents", tags=["incidents"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_service(session: SessionDependency) -> IncidentService:
    return IncidentService(IncidentRepository(session))


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentCreate, session: SessionDependency) -> IncidentRead:
    return await get_service(session).create(payload)


@router.get("", response_model=IncidentList)
async def list_incidents(
    session: SessionDependency,
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> IncidentList:
    incidents = await IncidentRepository(session).list(
        status=status_filter, limit=limit, offset=offset
    )
    return IncidentList(items=incidents, limit=limit, offset=offset)


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: str, session: SessionDependency) -> IncidentRead:
    incident = await IncidentRepository(session).get_by_incident_id(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentRead)
async def update_incident_status(
    incident_id: str, payload: IncidentStatusUpdate, session: SessionDependency
) -> IncidentRead:
    repository = IncidentRepository(session)
    incident = await repository.get_by_incident_id(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    try:
        return await IncidentService(repository).update_status(incident, payload.status)
    except InvalidStatusTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
