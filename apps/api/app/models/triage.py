import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.knowledge import enum_values


class TriageDecision(StrEnum):
    DRAFT_ALLOWED = "draft_allowed"
    HUMAN_ESCALATION = "human_escalation"


class TriageCategory(StrEnum):
    TROUBLESHOOTING = "troubleshooting"
    HOW_TO = "how_to"
    ACCOUNT_OR_BILLING = "account_or_billing"
    SECURITY_OR_PRIVACY = "security_or_privacy"
    UNCERTAIN = "uncertain"


class TicketTriageAssessment(Base):
    """A safe, structured outcome from the triage specialist, not its private reasoning."""

    __tablename__ = "ticket_triage_assessments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    decision: Mapped[TriageDecision] = mapped_column(
        Enum(TriageDecision, name="triage_decision", values_callable=enum_values)
    )
    category: Mapped[TriageCategory] = mapped_column(
        Enum(TriageCategory, name="triage_category", values_callable=enum_values)
    )
    reason: Mapped[str] = mapped_column(String(500))
    agent_name: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
