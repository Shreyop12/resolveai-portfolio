import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelSelectionPolicy(Base):
    """Human-owned thresholds used to interpret synthetic evaluation evidence."""

    __tablename__ = "model_selection_policies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), unique=True, index=True)
    min_grounding_rate: Mapped[float] = mapped_column(Float, default=0.8)
    min_average_human_score: Mapped[float] = mapped_column(Float, default=4.0)
    max_average_latency_ms: Mapped[int] = mapped_column(Integer, default=120_000)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), onupdate=lambda: datetime.now(UTC))
