import uuid

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft_evaluation import (
    DraftEvaluationCase,
    DraftEvaluationExperiment,
    DraftEvaluationJob,
    DraftEvaluationJobStatus,
    DraftEvaluationRun,
)


class DraftEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_case(self, case: DraftEvaluationCase) -> DraftEvaluationCase:
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def list_cases(self, workspace_id: uuid.UUID) -> list[DraftEvaluationCase]:
        result = await self.session.execute(
            select(DraftEvaluationCase)
            .where(DraftEvaluationCase.workspace_id == workspace_id)
            .order_by(DraftEvaluationCase.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_case(
        self, workspace_id: uuid.UUID, evaluation_id: str
    ) -> DraftEvaluationCase | None:
        result = await self.session.execute(
            select(DraftEvaluationCase).where(
                DraftEvaluationCase.workspace_id == workspace_id,
                DraftEvaluationCase.evaluation_id == evaluation_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_run(self, run: DraftEvaluationRun) -> DraftEvaluationRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def create_job(self, job: DraftEvaluationJob) -> DraftEvaluationJob:
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def create_experiment(
        self, experiment: DraftEvaluationExperiment
    ) -> DraftEvaluationExperiment:
        self.session.add(experiment)
        await self.session.commit()
        await self.session.refresh(experiment)
        return experiment

    async def list_experiments(self, workspace_id: uuid.UUID) -> list[DraftEvaluationExperiment]:
        result = await self.session.execute(
            select(DraftEvaluationExperiment)
            .where(DraftEvaluationExperiment.workspace_id == workspace_id)
            .order_by(DraftEvaluationExperiment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_job(self, job_id: str) -> DraftEvaluationJob | None:
        result = await self.session.execute(
            select(DraftEvaluationJob).where(DraftEvaluationJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_active_job(self, case_id: uuid.UUID) -> DraftEvaluationJob | None:
        result = await self.session.execute(
            select(DraftEvaluationJob)
            .where(
                DraftEvaluationJob.case_id == case_id,
                DraftEvaluationJob.status.in_(
                    [DraftEvaluationJobStatus.QUEUED, DraftEvaluationJobStatus.RUNNING]
                ),
            )
            .order_by(DraftEvaluationJob.created_at.desc())
        )
        return result.scalars().first()

    async def list_jobs(self, case_id: uuid.UUID) -> list[DraftEvaluationJob]:
        result = await self.session.execute(
            select(DraftEvaluationJob)
            .where(DraftEvaluationJob.case_id == case_id)
            .order_by(DraftEvaluationJob.created_at.desc())
        )
        return list(result.scalars().all())

    async def claim_job(self, job_id: str) -> DraftEvaluationJob | None:
        result = await self.session.execute(
            select(DraftEvaluationJob)
            .where(
                DraftEvaluationJob.job_id == job_id,
                DraftEvaluationJob.status == DraftEvaluationJobStatus.QUEUED,
            )
            .with_for_update(skip_locked=True)
        )
        job = result.scalar_one_or_none()
        return await self._mark_job_running(job)

    async def claim_next_queued_job(self) -> DraftEvaluationJob | None:
        """Atomically reserve one waiting job so concurrent workers cannot duplicate it."""
        result = await self.session.execute(
            select(DraftEvaluationJob)
            .where(DraftEvaluationJob.status == DraftEvaluationJobStatus.QUEUED)
            .order_by(DraftEvaluationJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return await self._mark_job_running(result.scalar_one_or_none())

    async def _mark_job_running(
        self, job: DraftEvaluationJob | None
    ) -> DraftEvaluationJob | None:
        if job is None:
            return None
        job.status = DraftEvaluationJobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.error_message = None
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def complete_job(self, job: DraftEvaluationJob) -> DraftEvaluationJob:
        job.status = DraftEvaluationJobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def fail_job(self, job: DraftEvaluationJob, error_message: str) -> DraftEvaluationJob:
        job.status = DraftEvaluationJobStatus.FAILED
        job.error_message = error_message[:500]
        job.finished_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def recover_unfinished_jobs(self) -> list[DraftEvaluationJob]:
        result = await self.session.execute(
            select(DraftEvaluationJob).where(
                DraftEvaluationJob.status.in_(
                    [DraftEvaluationJobStatus.QUEUED, DraftEvaluationJobStatus.RUNNING]
                )
            )
        )
        jobs = list(result.scalars().all())
        for job in jobs:
            job.status = DraftEvaluationJobStatus.QUEUED
            job.started_at = None
        if jobs:
            await self.session.commit()
            for job in jobs:
                await self.session.refresh(job)
        return jobs

    async def get_case_by_id(self, case_id: uuid.UUID) -> DraftEvaluationCase | None:
        result = await self.session.execute(
            select(DraftEvaluationCase).where(DraftEvaluationCase.id == case_id)
        )
        return result.scalar_one_or_none()

    async def list_runs(self, case_id: uuid.UUID) -> list[DraftEvaluationRun]:
        result = await self.session.execute(
            select(DraftEvaluationRun)
            .where(DraftEvaluationRun.case_id == case_id)
            .order_by(DraftEvaluationRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_runs_for_workspace(self, workspace_id: uuid.UUID) -> list[DraftEvaluationRun]:
        result = await self.session.execute(
            select(DraftEvaluationRun)
            .join(DraftEvaluationCase, DraftEvaluationRun.case_id == DraftEvaluationCase.id)
            .where(DraftEvaluationCase.workspace_id == workspace_id)
            .order_by(DraftEvaluationRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_run(self, case_id: uuid.UUID, run_id: str) -> DraftEvaluationRun | None:
        result = await self.session.execute(
            select(DraftEvaluationRun).where(
                DraftEvaluationRun.case_id == case_id,
                DraftEvaluationRun.run_id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def set_human_score(self, run: DraftEvaluationRun, score: int) -> DraftEvaluationRun:
        run.human_score = score
        await self.session.commit()
        await self.session.refresh(run)
        return run
