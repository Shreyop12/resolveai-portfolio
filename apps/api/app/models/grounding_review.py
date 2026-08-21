import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.knowledge import enum_values


class GroundingReviewDecision(StrEnum):
    GROUNDED = "grounded"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class TicketGroundingReview(Base):
    """A structured, non-sensitive verification outcome for a proposed draft."""

    __tablename__ = "ticket_grounding_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    review_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ticket_drafts.id"), nullable=True)
    decision: Mapped[GroundingReviewDecision] = mapped_column(
        Enum(GroundingReviewDecision, name="grounding_review_decision", values_callable=enum_values)
    )
    reason: Mapped[str] = mapped_column(String(500))
    source_article_ids: Mapped[list[str]] = mapped_column(JSON)
    agent_name: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
