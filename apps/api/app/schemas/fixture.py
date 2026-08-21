from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.incident import IncidentSeverity


class SyntheticIncidentInput(BaseModel):
    title: str
    description: str
    severity: IncidentSeverity


class ScenarioManifest(BaseModel):
    scenario_id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    description: str
    incident: SyntheticIncidentInput


class LogEvent(BaseModel):
    id: str
    timestamp: datetime
    service: str
    level: str
    message: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class MetricPoint(BaseModel):
    id: str
    timestamp: datetime
    metric: str
    value: float
    unit: str
    labels: dict[str, str] = Field(default_factory=dict)


class DeploymentChange(BaseModel):
    file: str
    summary: str


class DeploymentRecord(BaseModel):
    id: str
    service: str
    version: str
    started_at: datetime
    completed_at: datetime
    commit_sha: str
    changes: list[DeploymentChange]

    @model_validator(mode="after")
    def completion_follows_start(self) -> "DeploymentRecord":
        if self.completed_at < self.started_at:
            raise ValueError("Deployment completion cannot precede its start.")
        return self


class ExpectedRootCause(BaseModel):
    root_cause: str
    confidence: float = Field(ge=0, le=1)
    severity: IncidentSeverity
    evidence_ids: list[str] = Field(min_length=1)
    alternative_hypotheses: list[str] = Field(min_length=1)
    recommended_actions: list[str] = Field(min_length=1)


class SyntheticIncidentFixture(BaseModel):
    manifest: ScenarioManifest
    logs: list[LogEvent]
    metrics: list[MetricPoint]
    deployment: DeploymentRecord
    expected_root_cause: ExpectedRootCause
    git_diff: str

    @property
    def evidence_ids(self) -> set[str]:
        return {
            *(log.id for log in self.logs),
            *(metric.id for metric in self.metrics),
            self.deployment.id,
        }

    def validate_evidence_references(self) -> None:
        missing = set(self.expected_root_cause.evidence_ids) - self.evidence_ids
        if missing:
            missing_ids = ", ".join(sorted(missing))
            raise ValueError(f"Expected diagnosis references missing evidence: {missing_ids}")
