from pydantic import BaseModel, ConfigDict, Field


class ModelSelectionPolicyUpdate(BaseModel):
    min_grounding_rate: float = Field(ge=0, le=1)
    min_average_human_score: float = Field(ge=1, le=5)
    max_average_latency_ms: int = Field(ge=1_000, le=600_000)


class ModelSelectionPolicyRead(ModelSelectionPolicyUpdate):
    model_config = ConfigDict(from_attributes=True)


class ModelSelectionRecommendation(BaseModel):
    provider: str
    model: str
    status: str
    reasons: list[str]


class ModelSelectionReport(BaseModel):
    policy: ModelSelectionPolicyRead
    recommendations: list[ModelSelectionRecommendation]
