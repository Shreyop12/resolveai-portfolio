from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.draft_evaluation import (
    DraftEvaluationJobStatus,
    DraftEvaluationRunStatus,
    DraftQualityDecision,
)
from app.models.grounding_review import GroundingReviewDecision


class DraftEvaluationCaseCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=3, max_length=20_000)
    expected_article_id: str = Field(min_length=3, max_length=32)


class DraftEvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str
    subject: str
    message: str
    expected_article_id: str
    created_at: datetime


class DraftProviderAttemptRead(BaseModel):
    model: str
    outcome: str
    status_code: int | None = None


class DraftEvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    provider: str
    model: str
    status: DraftEvaluationRunStatus
    draft_body: str | None
    review_decision: GroundingReviewDecision | None
    review_reason: str | None
    error_message: str | None
    latency_ms: int
    draft_generation_latency_ms: int | None
    grounding_review_latency_ms: int | None
    provider_attempts: list[DraftProviderAttemptRead]
    quality_decision: DraftQualityDecision | None
    quality_reason: str | None
    human_score: int | None
    created_at: datetime


class DraftEvaluationRunScore(BaseModel):
    human_score: int = Field(ge=1, le=5)


class DraftEvaluationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: DraftEvaluationJobStatus
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class DraftEvaluationBatchRunRequest(BaseModel):
    evaluation_ids: list[str] = Field(min_length=1, max_length=20)


class DraftEvaluationBatchRunResult(BaseModel):
    queued_case_ids: list[str]
    job_ids: list[str]


class DraftEvaluationExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    evaluation_ids: list[str] = Field(min_length=1, max_length=20)


class DraftEvaluationExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experiment_id: str
    name: str
    case_ids: list[str]
    created_at: datetime


class DraftModelQualityMetric(BaseModel):
    provider: str
    model: str
    is_active: bool
    active_role: str | None
    total_runs: int
    completed_runs: int
    failed_runs: int
    grounding_pass_rate: float | None
    human_scored_runs: int
    average_human_score: float | None
    average_latency_ms: int | None


class ConfiguredDraftModel(BaseModel):
    provider: str
    model: str
    role: str


class DraftModelQualityReport(BaseModel):
    total_runs: int
    models: list[DraftModelQualityMetric]
    active_models: list[ConfiguredDraftModel]
