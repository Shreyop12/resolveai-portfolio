import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.draft import DraftReviewStatus


class TicketDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    draft_id: str
    body: str
    source_article_ids: list[str]
    coordinator_trace: list[str]
    status: DraftReviewStatus
    created_at: datetime
    reviewed_at: datetime | None


class TicketDraftReview(BaseModel):
    status: DraftReviewStatus
