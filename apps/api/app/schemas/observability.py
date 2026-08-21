import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.observability import CoordinatorRunStatus


class CoordinatorRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    status: CoordinatorRunStatus
    source_article_ids: list[str]
    stages: list[dict[str, object]]
    agent_models: dict[str, str]
    embedding_model: str
    chat_model: str
    elapsed_ms: int
    created_at: datetime


class RetrievalEvaluationCreate(BaseModel):
    query: str = Field(min_length=2, max_length=1_000)
    expected_article_id: str = Field(min_length=3, max_length=32)


class RetrievalEvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str
    query: str
    expected_article_id: str
    created_at: datetime


class RetrievalEvaluationResult(BaseModel):
    evaluation_id: str
    expected_article_id: str
    retrieved_article_ids: list[str]
    expected_rank: int | None
    hit_at_k: bool
    reciprocal_rank: float


class RetrievalEvaluationReport(BaseModel):
    total_cases: int
    hit_at_k: float
    mean_reciprocal_rank: float
    results: list[RetrievalEvaluationResult]
