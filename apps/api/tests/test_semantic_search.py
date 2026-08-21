from fastapi.testclient import TestClient

from tests.test_knowledge_base import create_article
from tests.test_support_workspace import client, create_workspace  # noqa: F401


def publish(client: TestClient, article_id: str) -> None:
    response = client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{article_id}/status",
        json={"status": "published"},
    )
    assert response.status_code == 200


def test_semantic_search_finds_a_meaning_match_without_keyword_overlap(client: TestClient) -> None:
    create_workspace(client)
    sso_article = create_article(client)
    billing_article = client.post(
        "/api/v1/workspaces/acme-support/knowledge-articles",
        json={
            "title": "Find an invoice",
            "category": "Billing",
            "body": "Account owners can download invoices from the billing page each month.",
        },
    ).json()
    publish(client, sso_article["article_id"])
    publish(client, billing_article["article_id"])

    response = client.get(
        "/api/v1/workspaces/acme-support/knowledge-articles/semantic-search?q=company+login+fails"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["article_id"] == sso_article["article_id"]
    assert response.json()["items"][0]["score"] == 1.0


def test_archiving_an_article_removes_it_from_semantic_search(client: TestClient) -> None:
    create_workspace(client)
    article = create_article(client)
    publish(client, article["article_id"])
    article_url = f"/api/v1/workspaces/acme-support/knowledge-articles/{article['article_id']}"

    archived = client.patch(f"{article_url}/status", json={"status": "archived"})
    search = client.get(
        "/api/v1/workspaces/acme-support/knowledge-articles/semantic-search?q=company+login"
    )

    assert archived.status_code == 200
    assert search.json()["items"] == []


def test_reindex_adds_vectors_for_existing_published_articles(client: TestClient) -> None:
    create_workspace(client)
    article = create_article(client)
    publish(client, article["article_id"])

    response = client.post("/api/v1/workspaces/acme-support/knowledge-articles/reindex")

    assert response.status_code == 200
    assert response.json() == {"indexed": 1, "model": "test-embedding-model"}
