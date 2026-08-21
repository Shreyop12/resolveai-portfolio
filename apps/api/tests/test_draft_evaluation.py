import asyncio
import uuid

from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from app.db.base import Base
from app.main import app
from app.models.draft_evaluation import (
    DraftEvaluationJob,
    DraftEvaluationJobStatus,
    DraftEvaluationRunStatus,
)
from app.models.grounding_review import GroundingReviewDecision
from app.repositories.draft_evaluations import DraftEvaluationRepository
from app.services.draft_evaluation import DraftModelComparisonService, DraftModelQualityService
from app.services.draft_evaluation_dispatcher import InlineDraftEvaluationDispatcher
from app.services.draft_evaluation_runner import process_draft_evaluation_job
from app.schemas.draft_evaluations import ConfiguredDraftModel
from app.schemas.model_selection import ModelSelectionPolicyRead
from app.services.model_selection import build_selection_report
from tests.test_knowledge_base import create_article
from tests.test_support_workspace import (  # noqa: F401
    client,
    create_workspace,
)


def publish(client: TestClient, article_id: str) -> None:
    response = client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{article_id}/status",
        json={"status": "published"},
    )
    assert response.status_code == 200


def create_case(client: TestClient, article_id: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces/acme-support/draft-evaluations",
        json={
            "subject": "Cannot sign in with SSO",
            "message": "Our company receives access denied when attempting to sign in.",
            "expected_article_id": article_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_queues_one_durable_comparison_job_without_creating_a_customer_draft(
    client: TestClient,
) -> None:
    create_workspace(client)
    article = create_article(client)
    publish(client, article["article_id"])
    case = create_case(client, article["article_id"])

    queued = client.post(
        f"/api/v1/workspaces/acme-support/draft-evaluations/{case['evaluation_id']}/run"
    )
    repeated_click = client.post(
        f"/api/v1/workspaces/acme-support/draft-evaluations/{case['evaluation_id']}/run"
    )
    jobs = client.get(
        f"/api/v1/workspaces/acme-support/draft-evaluations/{case['evaluation_id']}/jobs"
    )

    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    assert repeated_click.status_code == 202
    assert repeated_click.json()["job_id"] == queued.json()["job_id"]
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["job_id"] == queued.json()["job_id"]


def test_inline_dispatcher_runs_the_same_durable_job_in_the_api_process() -> None:
    background_tasks = BackgroundTasks()
    dispatcher = InlineDraftEvaluationDispatcher(background_tasks)

    asyncio.run(dispatcher.dispatch("DJOB-TEST"))

    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is process_draft_evaluation_job
    assert background_tasks.tasks[0].args == ("DJOB-TEST",)


def test_database_queue_claims_waiting_jobs_in_created_order() -> None:
    async def verify() -> None:
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            repository = DraftEvaluationRepository(session)
            await repository.create_job(
                DraftEvaluationJob(
                    job_id="DJOB-FIRST",
                    case_id=uuid.uuid4(),
                    status=DraftEvaluationJobStatus.QUEUED,
                )
            )
            await repository.create_job(
                DraftEvaluationJob(
                    job_id="DJOB-SECOND",
                    case_id=uuid.uuid4(),
                    status=DraftEvaluationJobStatus.QUEUED,
                )
            )

        async with session_factory() as session:
            repository = DraftEvaluationRepository(session)
            first = await repository.claim_next_queued_job()
            second = await repository.claim_next_queued_job()
            none_left = await repository.claim_next_queued_job()

        assert first is not None and first.job_id == "DJOB-FIRST"
        assert second is not None and second.job_id == "DJOB-SECOND"
        assert none_left is None
        await engine.dispose()

    asyncio.run(verify())


def test_does_not_queue_a_comparison_when_the_expected_source_is_not_published(
    client: TestClient,
) -> None:
    create_workspace(client)
    article = create_article(client)
    publish(client, article["article_id"])
    case = create_case(client, article["article_id"])
    archived = client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{article['article_id']}/status",
        json={"status": "archived"},
    )
    queued = client.post(
        f"/api/v1/workspaces/acme-support/draft-evaluations/{case['evaluation_id']}/run"
    )

    assert archived.status_code == 200
    assert queued.status_code == 422


def test_queues_selected_benchmark_cases_as_independent_jobs(client: TestClient) -> None:
    create_workspace(client)
    article = create_article(client)
    publish(client, article["article_id"])
    first_case = create_case(client, article["article_id"])
    second_case = create_case(client, article["article_id"])

    queued = client.post(
        "/api/v1/workspaces/acme-support/draft-evaluations/batch-run",
        json={
            "evaluation_ids": [
                first_case["evaluation_id"],
                second_case["evaluation_id"],
                first_case["evaluation_id"],
            ]
        },
    )

    assert queued.status_code == 202
    assert queued.json()["queued_case_ids"] == [
        first_case["evaluation_id"],
        second_case["evaluation_id"],
    ]
    assert len(queued.json()["job_ids"]) == 2


def test_saves_a_named_experiment_with_a_frozen_case_snapshot(client: TestClient) -> None:
    create_workspace(client)
    article = create_article(client)
    publish(client, article["article_id"])
    first_case = create_case(client, article["article_id"])
    second_case = create_case(client, article["article_id"])

    created = client.post(
        "/api/v1/workspaces/acme-support/draft-evaluations/experiments",
        json={
            "name": "SSO benchmark v1",
            "evaluation_ids": [first_case["evaluation_id"], second_case["evaluation_id"]],
        },
    )
    experiments = client.get("/api/v1/workspaces/acme-support/draft-evaluations/experiments")

    assert created.status_code == 202
    assert created.json()["name"] == "SSO benchmark v1"
    assert created.json()["case_ids"] == [first_case["evaluation_id"], second_case["evaluation_id"]]
    assert experiments.status_code == 200
    assert experiments.json()[0]["experiment_id"] == created.json()["experiment_id"]


def test_saves_model_selection_guardrails_and_reports_them(client: TestClient) -> None:
    create_workspace(client)

    saved = client.put(
        "/api/v1/workspaces/acme-support/model-selection-policy",
        json={
            "min_grounding_rate": 0.9,
            "min_average_human_score": 4.5,
            "max_average_latency_ms": 90_000,
        },
    )
    report = client.get("/api/v1/workspaces/acme-support/model-selection-policy/report")

    assert saved.status_code == 200
    assert report.status_code == 200
    assert report.json()["policy"] == saved.json()
    assert report.json()["recommendations"] == []


def test_reports_default_model_selection_guardrails_before_a_policy_is_saved(client: TestClient) -> None:
    create_workspace(client)

    report = client.get("/api/v1/workspaces/acme-support/model-selection-policy/report")

    assert report.status_code == 200
    assert report.json()["policy"] == {
        "min_grounding_rate": 0.8,
        "min_average_human_score": 4.0,
        "max_average_latency_ms": 120_000,
    }


def test_model_quality_summary_groups_actual_models_and_ignores_unscored_runs() -> None:
    report = DraftModelQualityService.summarize(
        [
            SimpleNamespace(
                provider="ollama",
                model="qwen3:4b",
                status=DraftEvaluationRunStatus.COMPLETED,
                review_decision=GroundingReviewDecision.GROUNDED,
                human_score=4,
                latency_ms=40_000,
            ),
            SimpleNamespace(
                provider="ollama",
                model="qwen3:4b",
                status=DraftEvaluationRunStatus.FAILED,
                review_decision=None,
                human_score=None,
                latency_ms=120_000,
            ),
            SimpleNamespace(
                provider="openrouter",
                model="example/free-model",
                status=DraftEvaluationRunStatus.COMPLETED,
                review_decision=GroundingReviewDecision.NEEDS_HUMAN_REVIEW,
                human_score=None,
                latency_ms=50_000,
            ),
        ],
        active_models=[
            ConfiguredDraftModel(
                provider="openrouter", model="example/free-model", role="hosted primary"
            )
        ],
    )

    ollama = next(metric for metric in report.models if metric.model == "qwen3:4b")
    openrouter = next(metric for metric in report.models if metric.provider == "openrouter")
    assert report.total_runs == 3
    assert ollama.total_runs == 2
    assert ollama.grounding_pass_rate == 1.0
    assert ollama.average_human_score == 4.0
    assert ollama.average_latency_ms == 80_000
    assert openrouter.grounding_pass_rate == 0.0
    assert openrouter.average_human_score is None
    assert ollama.is_active is False
    assert openrouter.is_active is True


def test_model_selection_only_recommends_configured_models() -> None:
    quality = DraftModelQualityService.summarize(
        [
            SimpleNamespace(
                provider="historical", model="retired", status=DraftEvaluationRunStatus.COMPLETED,
                review_decision=GroundingReviewDecision.GROUNDED, human_score=5, latency_ms=1_000,
            ),
            SimpleNamespace(
                provider="active", model="current", status=DraftEvaluationRunStatus.COMPLETED,
                review_decision=GroundingReviewDecision.GROUNDED, human_score=5, latency_ms=1_000,
            ),
        ],
        active_models=[ConfiguredDraftModel(provider="active", model="current", role="hosted primary")],
    )

    report = build_selection_report(
        ModelSelectionPolicyRead(
            min_grounding_rate=0.9, min_average_human_score=4.5, max_average_latency_ms=2_000
        ),
        quality,
    )

    assert [(item.provider, item.model) for item in report.recommendations] == [
        ("active", "current")
    ]


def test_runs_writers_concurrently_and_grounding_reviews_serially() -> None:
    tracker = {
        "active_writers": 0,
        "max_active_writers": 0,
        "active_reviews": 0,
        "max_active_reviews": 0,
    }

    class TimedWriter:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        async def complete(self, *, system: str, user: str) -> str:
            tracker["active_writers"] += 1
            tracker["max_active_writers"] = max(
                tracker["max_active_writers"], tracker["active_writers"]
            )
            await asyncio.sleep(0.02)
            tracker["active_writers"] -= 1
            return "Please confirm the verified domain before signing in again."

    class TimedReviewer:
        async def review(self, ticket, body, sources):
            tracker["active_reviews"] += 1
            tracker["max_active_reviews"] = max(
                tracker["max_active_reviews"], tracker["active_reviews"]
            )
            await asyncio.sleep(0.01)
            tracker["active_reviews"] -= 1
            return SimpleNamespace(
                decision=GroundingReviewDecision.GROUNDED,
                reason="Every instruction is supported by the source.",
            )

    class InMemoryRepository:
        def __init__(self) -> None:
            self.runs = []

        async def create_run(self, run):
            self.runs.append(run)
            return run

    repository = InMemoryRepository()
    service = DraftModelComparisonService(
        repository,
        TimedWriter("qwen3:4b"),
        TimedWriter("openai/gpt-oss-20b:free"),
        TimedReviewer(),
    )
    case = SimpleNamespace(
        id=uuid.uuid4(),
        evaluation_id="EVAL-TEST",
        workspace_id=uuid.uuid4(),
        subject="SSO access denied",
        message="Employees cannot sign in.",
    )
    article = SimpleNamespace(
        article_id="KB-TEST-001",
        title="SSO access",
        body="Confirm the verified domain before signing in again.",
    )

    runs = asyncio.run(service.compare(case, article))

    assert tracker["max_active_writers"] == 2
    assert tracker["max_active_reviews"] == 1
    assert len(runs) == 2
    for run in runs:
        assert run.status == DraftEvaluationRunStatus.COMPLETED
        assert run.draft_generation_latency_ms is not None
        assert run.grounding_review_latency_ms is not None
        assert run.latency_ms == (
            run.draft_generation_latency_ms + run.grounding_review_latency_ms
        )
