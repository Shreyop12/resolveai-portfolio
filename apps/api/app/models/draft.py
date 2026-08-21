import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.knowledge import enum_values


class DraftReviewStatus(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TicketDraft(Base):
    """A source-backed proposed response that always requires human review."""

    __tablename__ = "ticket_drafts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    source_article_ids: Mapped[list[str]] = mapped_column(JSON)
    coordinator_trace: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[DraftReviewStatus] = mapped_column(
        Enum(DraftReviewStatus, name="draft_review_status", values_callable=enum_values),
        default=DraftReviewStatus.AWAITING_REVIEW,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
