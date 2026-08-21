from app.schemas.draft_evaluations import DraftModelQualityReport
from app.schemas.model_selection import ModelSelectionPolicyRead, ModelSelectionRecommendation, ModelSelectionReport


def build_selection_report(policy: ModelSelectionPolicyRead, quality: DraftModelQualityReport) -> ModelSelectionReport:
    recommendations = []
    for metric in quality.models:
        if not metric.is_active or metric.total_runs == 0:
            continue
        reasons = []
        if metric.grounding_pass_rate is None or metric.grounding_pass_rate < policy.min_grounding_rate:
            reasons.append("grounding evidence is below the policy threshold")
        if metric.average_human_score is None or metric.average_human_score < policy.min_average_human_score:
            reasons.append("human feedback is below the policy threshold or missing")
        if metric.average_latency_ms is None or metric.average_latency_ms > policy.max_average_latency_ms:
            reasons.append("average latency exceeds the policy threshold")
        recommendations.append(ModelSelectionRecommendation(provider=metric.provider, model=metric.model, status="eligible" if not reasons else "not_eligible", reasons=reasons))
    return ModelSelectionReport(policy=policy, recommendations=recommendations)
