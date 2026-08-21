import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.knowledge import enum_values


class CoordinatorRunStatus(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class CoordinatorRun(Base):
    """Non-sensitive operational trace for one coordinator attempt."""

    __tablename__ = "coordinator_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ticket_drafts.id"), nullable=True
    )
    status: Mapped[CoordinatorRunStatus] = mapped_column(
        Enum(CoordinatorRunStatus, name="coordinator_run_status", values_callable=enum_values)
    )
    source_article_ids: Mapped[list[str]] = mapped_column(JSON)
    stages: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    agent_models: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    embedding_model: Mapped[str] = mapped_column(String(120))
    chat_model: Mapped[str] = mapped_column(String(120))
    elapsed_ms: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RetrievalEvaluationCase(Base):
    """A human-defined expectation used to measure retrieval quality."""

    __tablename__ = "retrieval_evaluation_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    query: Mapped[str] = mapped_column(String(1_000))
    expected_article_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
