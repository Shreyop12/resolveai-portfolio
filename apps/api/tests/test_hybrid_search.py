from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.services.hybrid_search import fuse_ranked_results
from tests.test_knowledge_base import create_article
from tests.test_support_workspace import client, create_workspace  # noqa: F401


def test_reciprocal_rank_fusion_rewards_an_article_found_by_both_methods() -> None:
    keyword_first = SimpleNamespace(article_id="KB-KEYWORD")
    shared = SimpleNamespace(article_id="KB-SHARED")
    semantic_only = SimpleNamespace(article_id="KB-SEMANTIC")

    matches = fuse_ranked_results(
        [(keyword_first, 0.9), (shared, 0.8)],
        [(shared, 0.9), (semantic_only, 0.8)],
        limit=3,
        rrf_constant=10,
    )

    assert [match.article.article_id for match in matches] == [
        "KB-SHARED",
        "KB-KEYWORD",
        "KB-SEMANTIC",
    ]
    assert matches[0].keyword_rank == 2
    assert matches[0].semantic_rank == 1


def test_hybrid_search_returns_explainable_published_matches(client: TestClient) -> None:
    create_workspace(client)
    published_article = create_article(client)
    draft_article = client.post(
        "/api/v1/workspaces/acme-support/knowledge-articles",
        json={
            "title": "SSO draft guidance",
            "category": "Authentication",
            "body": "This unfinished guide must never become an AI retrieval source.",
        },
    ).json()
    publish = client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{published_article['article_id']}/status",
        json={"status": "published"},
    )

    response = client.get(
        "/api/v1/workspaces/acme-support/knowledge-articles/hybrid-search?q=company+login+SSO"
    )

    assert publish.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["fusion_method"] == "reciprocal_rank_fusion"
    assert payload["items"][0]["article_id"] == published_article["article_id"]
    assert payload["items"][0]["keyword_rank"] == 1
    assert payload["items"][0]["semantic_rank"] == 1
    assert draft_article["article_id"] not in [item["article_id"] for item in payload["items"]]
