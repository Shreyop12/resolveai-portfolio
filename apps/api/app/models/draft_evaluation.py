import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.grounding_review import GroundingReviewDecision
from app.models.knowledge import enum_values


class DraftEvaluationRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class DraftQualityDecision(StrEnum):
    PASSED = "passed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class DraftEvaluationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DraftEvaluationCase(Base):
    """A synthetic, source-backed prompt used only for model comparison."""

    __tablename__ = "draft_evaluation_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    expected_article_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class DraftEvaluationRun(Base):
    """One writer's result for a synthetic evaluation case, never a customer draft."""

    __tablename__ = "draft_evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("draft_evaluation_cases.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(160))
    status: Mapped[DraftEvaluationRunStatus] = mapped_column(
        Enum(DraftEvaluationRunStatus, name="draft_evaluation_run_status", values_callable=enum_values)
    )
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_decision: Mapped[GroundingReviewDecision | None] = mapped_column(
        Enum(GroundingReviewDecision, name="grounding_review_decision", values_callable=enum_values),
        nullable=True,
    )
    review_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    draft_generation_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grounding_review_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_attempts: Mapped[list[dict[str, str | int | None]]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    quality_decision: Mapped[DraftQualityDecision | None] = mapped_column(String(32), nullable=True)
    quality_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    human_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class DraftEvaluationJob(Base):
    """Durable background-work record for one two-writer comparison."""

    __tablename__ = "draft_evaluation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("draft_evaluation_cases.id"), index=True)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("draft_evaluation_experiments.id"), index=True, nullable=True
    )
    status: Mapped[DraftEvaluationJobStatus] = mapped_column(
        Enum(DraftEvaluationJobStatus, name="draft_evaluation_job_status", values_callable=enum_values)
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class DraftEvaluationExperiment(Base):
    """A named, frozen selection of synthetic cases for repeatable comparison."""

    __tablename__ = "draft_evaluation_experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    case_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
