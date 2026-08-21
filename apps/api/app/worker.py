"""Background process for slow, source-grounded draft model comparisons."""

import asyncio
import logging

from app.db.session import SessionLocal
from app.repositories.draft_evaluations import DraftEvaluationRepository
from app.services.draft_evaluation_queue import DraftEvaluationQueue
from app.services.draft_evaluation_runner import (
    process_draft_evaluation_job,
    process_next_draft_evaluation_job,
)

logger = logging.getLogger(__name__)


async def recover_jobs(queue: DraftEvaluationQueue) -> None:
    async with SessionLocal() as session:
        jobs = await DraftEvaluationRepository(session).recover_unfinished_jobs()
    for job in jobs:
        await queue.enqueue(job.job_id)
    if jobs:
        logger.info("Re-queued %s unfinished draft evaluation job(s).", len(jobs))


async def run_worker() -> None:
    from redis.asyncio import Redis

    from app.core.config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    if settings.draft_evaluation_execution_mode == "database":
        await recover_jobs_for_database_queue()
        logger.info("Draft evaluation database worker is ready.")
        while True:
            if not await process_next_draft_evaluation_job():
                await asyncio.sleep(2)

    queue = DraftEvaluationQueue(Redis.from_url(settings.redis_url, decode_responses=True))
    try:
        await recover_jobs(queue)
        logger.info("Draft evaluation worker is ready.")
        while True:
            job_id = await queue.dequeue()
            if job_id:
                await process_draft_evaluation_job(job_id)
    finally:
        await queue.close()


async def recover_jobs_for_database_queue() -> None:
    async with SessionLocal() as session:
        jobs = await DraftEvaluationRepository(session).recover_unfinished_jobs()
    if jobs:
        logger.info("Returned %s unfinished draft evaluation job(s) to the database queue.", len(jobs))


if __name__ == "__main__":
    asyncio.run(run_worker())
