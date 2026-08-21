from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.support import require_workspace
from app.db.session import get_session
from app.models.model_selection import ModelSelectionPolicy
from app.repositories.draft_evaluations import DraftEvaluationRepository
from app.repositories.model_selection import ModelSelectionPolicyRepository
from app.schemas.model_selection import ModelSelectionPolicyRead, ModelSelectionPolicyUpdate, ModelSelectionReport
from app.services.draft_evaluation import DraftModelQualityService
from app.services.model_selection import build_selection_report

router = APIRouter(prefix="/workspaces/{workspace_slug}/model-selection-policy", tags=["model selection"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def policy_for_workspace(session: AsyncSession, workspace_id):
    repository = ModelSelectionPolicyRepository(session)
    saved_policy = await repository.get(workspace_id)
    if saved_policy:
        return saved_policy
    # SQLAlchemy column defaults are applied when a row is inserted, not when an
    # unsaved object is created. The report endpoint also needs usable defaults.
    return ModelSelectionPolicy(
        workspace_id=workspace_id,
        min_grounding_rate=0.8,
        min_average_human_score=4.0,
        max_average_latency_ms=120_000,
    )


@router.get("", response_model=ModelSelectionPolicyRead)
async def get_policy(workspace_slug: str, session: SessionDependency) -> ModelSelectionPolicyRead:
    workspace = await require_workspace(workspace_slug, session)
    return await policy_for_workspace(session, workspace.id)


@router.put("", response_model=ModelSelectionPolicyRead)
async def save_policy(workspace_slug: str, payload: ModelSelectionPolicyUpdate, session: SessionDependency) -> ModelSelectionPolicyRead:
    workspace = await require_workspace(workspace_slug, session)
    policy = await policy_for_workspace(session, workspace.id)
    policy.min_grounding_rate = payload.min_grounding_rate
    policy.min_average_human_score = payload.min_average_human_score
    policy.max_average_latency_ms = payload.max_average_latency_ms
    return await ModelSelectionPolicyRepository(session).save(policy)


@router.get("/report", response_model=ModelSelectionReport)
async def get_report(workspace_slug: str, session: SessionDependency) -> ModelSelectionReport:
    workspace = await require_workspace(workspace_slug, session)
    policy = await policy_for_workspace(session, workspace.id)
    runs = await DraftEvaluationRepository(session).list_runs_for_workspace(workspace.id)
    return build_selection_report(ModelSelectionPolicyRead.model_validate(policy), DraftModelQualityService.summarize(runs))
