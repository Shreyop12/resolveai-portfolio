"""Choose how synthetic evaluation jobs start in local and free-cloud environments."""

from typing import Protocol

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.services.draft_evaluation_queue import DraftEvaluationQueue
from app.services.draft_evaluation_runner import process_draft_evaluation_job


class DraftEvaluationDispatcher(Protocol):
    async def dispatch(self, job_id: str) -> None: ...


class QueuedDraftEvaluationDispatcher:
    """Production-style dispatcher: Redis holds the job for a dedicated worker."""

    def __init__(self, queue: DraftEvaluationQueue) -> None:
        self.queue = queue

    async def dispatch(self, job_id: str) -> None:
        try:
            await self.queue.enqueue(job_id)
        finally:
            await self.queue.close()


class InlineDraftEvaluationDispatcher:
    """Free-demo dispatcher: schedule work in the API process after its HTTP response."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self.background_tasks = background_tasks

    async def dispatch(self, job_id: str) -> None:
        self.background_tasks.add_task(process_draft_evaluation_job, job_id)


class DatabaseDraftEvaluationDispatcher:
    """Postgres is already the durable queue; the polling worker discovers this job."""

    async def dispatch(self, job_id: str) -> None:
        return None


def get_draft_evaluation_dispatcher(
    background_tasks: BackgroundTasks,
) -> DraftEvaluationDispatcher:
    execution_mode = get_settings().draft_evaluation_execution_mode
    if execution_mode == "inline":
        return InlineDraftEvaluationDispatcher(background_tasks)
    if execution_mode == "database":
        return DatabaseDraftEvaluationDispatcher()

    from redis.asyncio import Redis

    queue = DraftEvaluationQueue(
        Redis.from_url(get_settings().redis_url, decode_responses=True)
    )
    return QueuedDraftEvaluationDispatcher(queue)
