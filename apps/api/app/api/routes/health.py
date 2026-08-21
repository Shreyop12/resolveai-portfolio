from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness endpoint used by Docker and load balancers."""
    return HealthResponse(status="ok", service="resolveai-api")


@router.get("/ready", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def ready() -> HealthResponse:
    """Foundation readiness endpoint; dependency probes arrive with persistence."""
    return HealthResponse(status="ready", service="resolveai-api")
