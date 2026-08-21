from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from app.core.config import get_settings

QUEUE_KEY = "resolveai:draft-evaluation-jobs"


class DraftEvaluationQueue:
    """Small Redis mailbox. PostgreSQL remains the durable source of job state."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def enqueue(self, job_id: str) -> None:
        await self.redis.lpush(QUEUE_KEY, job_id)

    async def dequeue(self, timeout_seconds: int = 5) -> str | None:
        item = await self.redis.brpop(QUEUE_KEY, timeout=timeout_seconds)
        return item[1] if item else None

    async def close(self) -> None:
        await self.redis.aclose()


async def get_draft_evaluation_queue() -> AsyncGenerator[DraftEvaluationQueue, None]:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    queue = DraftEvaluationQueue(redis)
    try:
        yield queue
    finally:
        await queue.close()
