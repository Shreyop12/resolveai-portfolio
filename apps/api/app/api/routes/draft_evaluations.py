import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.support import require_workspace
from app.db.session import get_session
from app.models.draft_evaluation import (
    DraftEvaluationCase,
    DraftEvaluationExperiment,
    DraftEvaluationJob,
    DraftEvaluationJobStatus,
)
from app.models.knowledge import ArticleStatus
from app.repositories.draft_evaluations import DraftEvaluationRepository
from app.repositories.knowledge import KnowledgeArticleRepository
from app.schemas.draft_evaluations import (
    DraftEvaluationCaseCreate,
    DraftEvaluationCaseRead,
    DraftEvaluationBatchRunRequest,
    DraftEvaluationBatchRunResult,
    DraftEvaluationExperimentCreate,
    DraftEvaluationExperimentRead,
    DraftEvaluationJobRead,
    DraftModelQualityReport,
    DraftEvaluationRunRead,
    DraftEvaluationRunScore,
)
from app.services.draft_evaluation_dispatcher import (
    DraftEvaluationDispatcher,
    get_draft_evaluation_dispatcher,
)
from app.services.draft_evaluation import DraftModelQualityService

router = APIRouter(prefix="/workspaces/{workspace_slug}/draft-evaluations", tags=["draft model evaluation"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
DispatcherDependency = Annotated[
    DraftEvaluationDispatcher, Depends(get_draft_evaluation_dispatcher)
]


async def require_case(workspace_id: uuid.UUID, evaluation_id: str, session: AsyncSession) -> DraftEvaluationCase:
    case = await DraftEvaluationRepository(session).get_case(workspace_id, evaluation_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft evaluation case not found.")
    return case


@router.post("", response_model=DraftEvaluationCaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    workspace_slug: str, payload: DraftEvaluationCaseCreate, session: SessionDependency
) -> DraftEvaluationCaseRead:
    workspace = await require_workspace(workspace_slug, session)
    article = await KnowledgeArticleRepository(session).get_by_article_id(
        workspace_id=workspace.id, article_id=payload.expected_article_id
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expected knowledge article not found.")
    if article.status != ArticleStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A draft evaluation case must use a published knowledge article.",
        )
    return await DraftEvaluationRepository(session).create_case(
        DraftEvaluationCase(
            evaluation_id=f"DVAL-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
            workspace_id=workspace.id,
            subject=payload.subject,
            message=payload.message,
            expected_article_id=payload.expected_article_id,
        )
    )


@router.get("", response_model=list[DraftEvaluationCaseRead])
async def list_cases(workspace_slug: str, session: SessionDependency) -> list[DraftEvaluationCaseRead]:
    workspace = await require_workspace(workspace_slug, session)
    return await DraftEvaluationRepository(session).list_cases(workspace.id)


@router.get("/report", response_model=DraftModelQualityReport)
async def get_model_quality_report(
    workspace_slug: str, session: SessionDependency
) -> DraftModelQualityReport:
    workspace = await require_workspace(workspace_slug, session)
    runs = await DraftEvaluationRepository(session).list_runs_for_workspace(workspace.id)
    return DraftModelQualityService.summarize(runs)


async def enqueue_comparison_job(
    repository: DraftEvaluationRepository,
    case: DraftEvaluationCase,
    dispatcher: DraftEvaluationDispatcher,
    experiment_id: uuid.UUID | None = None,
) -> DraftEvaluationJob:
    active_job = await repository.get_active_job(case.id)
    if active_job is not None:
        return active_job
    job = await repository.create_job(
        DraftEvaluationJob(
            job_id=f"DJOB-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
            case_id=case.id,
            experiment_id=experiment_id,
            status=DraftEvaluationJobStatus.QUEUED,
        )
    )
    await dispatcher.dispatch(job.job_id)
    return job


@router.post("/experiments", response_model=DraftEvaluationExperimentRead, status_code=status.HTTP_202_ACCEPTED)
async def create_experiment(
    workspace_slug: str,
    payload: DraftEvaluationExperimentCreate,
    session: SessionDependency,
    dispatcher: DispatcherDependency,
) -> DraftEvaluationExperimentRead:
    workspace = await require_workspace(workspace_slug, session)
    requested_case_ids = list(dict.fromkeys(payload.evaluation_ids))
    repository = DraftEvaluationRepository(session)
    cases: list[DraftEvaluationCase] = []
    for evaluation_id in requested_case_ids:
        case = await require_case(workspace.id, evaluation_id, session)
        article = await KnowledgeArticleRepository(session).get_by_article_id(
            workspace_id=workspace.id, article_id=case.expected_article_id
        )
        if article is None or article.status != ArticleStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"The expected evaluation source for {evaluation_id} must remain published.",
            )
        cases.append(case)
    experiment = await repository.create_experiment(
        DraftEvaluationExperiment(
            experiment_id=f"EXP-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}",
            workspace_id=workspace.id,
            name=payload.name,
            case_ids=[case.evaluation_id for case in cases],
        )
    )
    for case in cases:
        await enqueue_comparison_job(repository, case, dispatcher, experiment.id)
    return experiment


@router.get("/experiments", response_model=list[DraftEvaluationExperimentRead])
async def list_experiments(
    workspace_slug: str, session: SessionDependency
) -> list[DraftEvaluationExperimentRead]:
    workspace = await require_workspace(workspace_slug, session)
    return await DraftEvaluationRepository(session).list_experiments(workspace.id)


@router.post("/batch-run", response_model=DraftEvaluationBatchRunResult, status_code=status.HTTP_202_ACCEPTED)
async def run_comparison_batch(
    workspace_slug: str,
    payload: DraftEvaluationBatchRunRequest,
    session: SessionDependency,
    dispatcher: DispatcherDependency,
) -> DraftEvaluationBatchRunResult:
    workspace = await require_workspace(workspace_slug, session)
    requested_case_ids = list(dict.fromkeys(payload.evaluation_ids))
    repository = DraftEvaluationRepository(session)
    cases: list[DraftEvaluationCase] = []
    for evaluation_id in requested_case_ids:
        case = await require_case(workspace.id, evaluation_id, session)
        article = await KnowledgeArticleRepository(session).get_by_article_id(
            workspace_id=workspace.id, article_id=case.expected_article_id
        )
        if article is None or article.status != ArticleStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"The expected evaluation source for {evaluation_id} must remain published.",
            )
        cases.append(case)

    jobs = [await enqueue_comparison_job(repository, case, dispatcher) for case in cases]
    return DraftEvaluationBatchRunResult(
        queued_case_ids=[case.evaluation_id for case in cases],
        job_ids=[job.job_id for job in jobs],
    )


@router.post(
    "/{evaluation_id}/run",
    response_model=DraftEvaluationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_comparison(
    workspace_slug: str,
    evaluation_id: str,
    session: SessionDependency,
    dispatcher: DispatcherDependency,
) -> DraftEvaluationJobRead:
    workspace = await require_workspace(workspace_slug, session)
    case = await require_case(workspace.id, evaluation_id, session)
    article = await KnowledgeArticleRepository(session).get_by_article_id(
        workspace_id=workspace.id, article_id=case.expected_article_id
    )
    if article is None or article.status != ArticleStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The expected evaluation source must remain published.",
        )
    return await enqueue_comparison_job(DraftEvaluationRepository(session), case, dispatcher)


@router.get("/{evaluation_id}/jobs", response_model=list[DraftEvaluationJobRead])
async def list_jobs(
    workspace_slug: str, evaluation_id: str, session: SessionDependency
) -> list[DraftEvaluationJobRead]:
    workspace = await require_workspace(workspace_slug, session)
    case = await require_case(workspace.id, evaluation_id, session)
    return await DraftEvaluationRepository(session).list_jobs(case.id)


@router.get("/{evaluation_id}/runs", response_model=list[DraftEvaluationRunRead])
async def list_runs(
    workspace_slug: str, evaluation_id: str, session: SessionDependency
) -> list[DraftEvaluationRunRead]:
    workspace = await require_workspace(workspace_slug, session)
    case = await require_case(workspace.id, evaluation_id, session)
    return await DraftEvaluationRepository(session).list_runs(case.id)


@router.patch("/{evaluation_id}/runs/{run_id}", response_model=DraftEvaluationRunRead)
async def score_run(
    workspace_slug: str,
    evaluation_id: str,
    run_id: str,
    payload: DraftEvaluationRunScore,
    session: SessionDependency,
) -> DraftEvaluationRunRead:
    workspace = await require_workspace(workspace_slug, session)
    case = await require_case(workspace.id, evaluation_id, session)
    run = await DraftEvaluationRepository(session).get_run(case.id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft evaluation run not found.")
    return await DraftEvaluationRepository(session).set_human_score(run, payload.human_score)
