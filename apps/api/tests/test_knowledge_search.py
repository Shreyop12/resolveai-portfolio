from fastapi.testclient import TestClient

from tests.test_knowledge_base import create_article
from tests.test_support_workspace import client, create_workspace  # noqa: F401


def publish_article(client: TestClient, article_id: str, workspace_slug: str = "acme-support") -> None:
    response = client.patch(
        f"/api/v1/workspaces/{workspace_slug}/knowledge-articles/{article_id}/status",
        json={"status": "published"},
    )
    assert response.status_code == 200


def test_keyword_search_returns_ranked_published_sources(client: TestClient) -> None:
    create_workspace(client)
    title_match = create_article(client)
    body_match = client.post(
        "/api/v1/workspaces/acme-support/knowledge-articles",
        json={
            "title": "Access troubleshooting guide",
            "category": "Authentication",
            "body": "Use this guide when a customer cannot sign in through enterprise SSO.",
        },
    ).json()
    publish_article(client, title_match["article_id"])
    publish_article(client, body_match["article_id"])

    response = client.get(
        "/api/v1/workspaces/acme-support/knowledge-articles/search?q=enterprise+SSO"
    )

    assert response.status_code == 200
    assert [item["article_id"] for item in response.json()["items"]] == [
        title_match["article_id"],
        body_match["article_id"],
    ]
    assert response.json()["items"][0]["score"] > response.json()["items"][1]["score"]


def test_keyword_search_excludes_drafts_and_other_workspaces(client: TestClient) -> None:
    create_workspace(client)
    draft = create_article(client)
    client.post("/api/v1/workspaces", json={"name": "Beta Support", "slug": "beta-support"})
    beta_article = create_article(client, "beta-support")
    publish_article(client, beta_article["article_id"], "beta-support")

    response = client.get(
        "/api/v1/workspaces/acme-support/knowledge-articles/search?q=enterprise+SSO"
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert draft["status"] == "draft"
