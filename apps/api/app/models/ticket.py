import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class TicketStatus(StrEnum):
    OPEN = "open"
    DRAFTING = "drafting"
    AWAITING_REVIEW = "awaiting_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NoteAuthor(StrEnum):
    SUPPORT_AGENT = "support_agent"
    SYSTEM = "system"


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    """Store the user-facing enum value instead of its Python member name."""
    return [member.value for member in enum_type]


class SupportTicket(Base):
    """One customer question moving through the ResolveAI support workflow."""

    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status", values_callable=enum_values),
        default=TicketStatus.OPEN,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority", values_callable=enum_values),
        default=TicketPriority.NORMAL,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    workspace: Mapped["Workspace"] = relationship(back_populates="tickets")
    notes: Mapped[list["TicketNote"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketNote(Base):
    """An internal support note; AI drafts will be represented separately later."""

    __tablename__ = "ticket_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    author: Mapped[NoteAuthor] = mapped_column(
        Enum(NoteAuthor, name="note_author", values_callable=enum_values)
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ticket: Mapped[SupportTicket] = relationship(back_populates="notes")
