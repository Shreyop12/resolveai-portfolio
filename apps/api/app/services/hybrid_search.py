from dataclasses import dataclass

from app.models.knowledge import KnowledgeArticle

RRF_CONSTANT = 60


@dataclass(frozen=True)
class HybridSearchMatch:
    article: KnowledgeArticle
    fusion_score: float
    keyword_rank: int | None
    semantic_rank: int | None


def fuse_ranked_results(
    keyword_results: list[tuple[KnowledgeArticle, float]],
    semantic_results: list[tuple[KnowledgeArticle, float]],
    *,
    limit: int,
    rrf_constant: int = RRF_CONSTANT,
) -> list[HybridSearchMatch]:
    """Merge independently ranked retrieval lists without mixing incompatible scores."""
    merged: dict[str, dict[str, object]] = {}
    for label, results in (("keyword", keyword_results), ("semantic", semantic_results)):
        for rank, (article, _) in enumerate(results, start=1):
            item = merged.setdefault(
                article.article_id,
                {"article": article, "score": 0.0, "keyword_rank": None, "semantic_rank": None},
            )
            item["score"] = float(item["score"]) + 1 / (rrf_constant + rank)
            item[f"{label}_rank"] = rank

    matches = [
        HybridSearchMatch(
            article=item["article"],  # type: ignore[arg-type]
            fusion_score=float(item["score"]),
            keyword_rank=item["keyword_rank"],  # type: ignore[arg-type]
            semantic_rank=item["semantic_rank"],  # type: ignore[arg-type]
        )
        for item in merged.values()
    ]
    return sorted(
        matches,
        key=lambda match: (
            -match.fusion_score,
            min(rank for rank in (match.keyword_rank, match.semantic_rank) if rank is not None),
            match.article.article_id,
        ),
    )[:limit]
