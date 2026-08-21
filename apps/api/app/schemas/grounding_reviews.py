from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.grounding_review import GroundingReviewDecision


class TicketGroundingReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    decision: GroundingReviewDecision
    reason: str
    source_article_ids: list[str]
    agent_name: str
    model: str
    created_at: datetime
