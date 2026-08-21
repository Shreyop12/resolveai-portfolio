from fastapi.testclient import TestClient

from tests.test_knowledge_base import create_article
from tests.test_support_workspace import client, create_workspace  # noqa: F401


def publish(client: TestClient, article_id: str) -> None:
    response = client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{article_id}/status",
        json={"status": "published"},
    )
    assert response.status_code == 200


def test_evaluation_measures_hybrid_retrieval_against_a_human_expected_source(
    client: TestClient,
) -> None:
    create_workspace(client)
    expected_article = create_article(client)
    publish(client, expected_article["article_id"])

    created = client.post(
        "/api/v1/workspaces/acme-support/retrieval-evaluations",
        json={
            "query": "company login SSO access denied",
            "expected_article_id": expected_article["article_id"],
        },
    )
    report = client.post("/api/v1/workspaces/acme-support/retrieval-evaluations/run")

    assert created.status_code == 201
    assert report.status_code == 200
    assert report.json()["total_cases"] == 1
    assert report.json()["hit_at_k"] == 1.0
    assert report.json()["mean_reciprocal_rank"] == 1.0
    assert report.json()["results"][0]["expected_rank"] == 1


def test_evaluation_requires_a_published_expected_source(client: TestClient) -> None:
    create_workspace(client)
    draft_article = create_article(client)

    response = client.post(
        "/api/v1/workspaces/acme-support/retrieval-evaluations",
        json={"query": "enterprise SSO", "expected_article_id": draft_article["article_id"]},
    )

    assert response.status_code == 422
    assert "published knowledge article" in response.json()["detail"]
