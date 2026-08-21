from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.triage import TriageCategory, TriageDecision


class TicketTriageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: str
    decision: TriageDecision
    category: TriageCategory
    reason: str
    agent_name: str
    model: str
    created_at: datetime
