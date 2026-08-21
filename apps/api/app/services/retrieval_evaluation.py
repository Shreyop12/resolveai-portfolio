import uuid
from dataclasses import dataclass

from app.models.observability import RetrievalEvaluationCase
from app.repositories.knowledge import KnowledgeArticleRepository
from app.services.embeddings import EmbeddingClient
from app.services.hybrid_search import fuse_ranked_results


@dataclass(frozen=True)
class EvaluationOutcome:
    case: RetrievalEvaluationCase
    retrieved_article_ids: list[str]
    expected_rank: int | None

    @property
    def reciprocal_rank(self) -> float:
        return 0.0 if self.expected_rank is None else 1 / self.expected_rank


class HybridRetrievalEvaluator:
    def __init__(self, repository: KnowledgeArticleRepository, embedding_client: EmbeddingClient) -> None:
        self.repository = repository
        self.embedding_client = embedding_client

    async def evaluate(
        self, *, workspace_id: uuid.UUID, cases: list[RetrievalEvaluationCase], limit: int
    ) -> list[EvaluationOutcome]:
        outcomes: list[EvaluationOutcome] = []
        for case in cases:
            embedding = await self.embedding_client.embed(case.query)
            keyword_results = await self.repository.search_published(
                workspace_id=workspace_id, query=case.query, limit=max(limit * 4, 20)
            )
            semantic_results = await self.repository.search_semantic(
                workspace_id=workspace_id, embedding=embedding, limit=max(limit * 4, 20)
            )
            article_ids = [
                match.article.article_id
                for match in fuse_ranked_results(keyword_results, semantic_results, limit=limit)
            ]
            rank = next(
                (index for index, article_id in enumerate(article_ids, start=1) if article_id == case.expected_article_id),
                None,
            )
            outcomes.append(EvaluationOutcome(case, article_ids, rank))
        return outcomes
