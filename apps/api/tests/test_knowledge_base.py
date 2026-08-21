from fastapi.testclient import TestClient

from tests.test_support_workspace import client, create_workspace  # noqa: F401


def create_article(client: TestClient, workspace_slug: str = "acme-support") -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_slug}/knowledge-articles",
        json={
            "title": "Set up enterprise SSO",
            "category": "Authentication",
            "body": "Ask an account owner to verify the SAML metadata and domain settings.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_new_knowledge_article_starts_as_a_draft(client: TestClient) -> None:
    create_workspace(client)

    article = create_article(client)

    assert article["article_id"].startswith("KB-2026-")
    assert article["status"] == "draft"
    assert article["published_at"] is None


def test_imported_text_document_becomes_a_reviewable_draft(client: TestClient) -> None:
    create_workspace(client)

    response = client.post(
        "/api/v1/workspaces/acme-support/knowledge-articles/documents/import-text",
        json={
            "source_file_name": "enterprise-sso-policy.md",
            "category": "Authentication",
            "content": "Verify the customer domain and compare the current SAML metadata before troubleshooting access.",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "enterprise sso policy"
    assert response.json()["status"] == "draft"
    assert response.json()["chunk_count"] == 1


def test_document_ingestion_splits_markdown_headings_into_traceable_chunks(client: TestClient) -> None:
    create_workspace(client)

    response = client.post(
        "/api/v1/workspaces/acme-support/knowledge-articles/documents/import-text",
        json={
            "source_file_name": "support-handbook.md",
            "category": "Support",
            "content": "# Sign in\n\nConfirm the verified domain before checking SAML metadata.\n\n# Billing\n\nAdministrators can download invoices from Billing settings.",
        },
    )
    documents = client.get("/api/v1/workspaces/acme-support/knowledge-articles/documents")
    articles = client.get("/api/v1/workspaces/acme-support/knowledge-articles")

    assert response.status_code == 201
    assert response.json()["chunk_count"] == 2
    assert documents.json()["items"][0]["source_file_name"] == "support-handbook.md"
    assert len(articles.json()["items"]) == 2


def test_deleting_a_draft_document_removes_its_chunks(client: TestClient) -> None:
    create_workspace(client)
    imported = client.post(
        "/api/v1/workspaces/acme-support/knowledge-articles/documents/import-text",
        json={
            "source_file_name": "draft-handbook.md",
            "category": "Support",
            "content": "# One\n\nA complete source section with enough content to be valid.\n\n# Two\n\nAnother complete source section with enough content to be valid.",
        },
    )

    deleted = client.delete(f"/api/v1/workspaces/acme-support/knowledge-articles/documents/{imported.json()['document_id']}")
    articles = client.get("/api/v1/workspaces/acme-support/knowledge-articles")
    documents = client.get("/api/v1/workspaces/acme-support/knowledge-articles/documents")

    assert deleted.status_code == 204
    assert articles.json()["items"] == []
    assert documents.json()["items"] == []


def test_articles_are_scoped_to_their_workspace(client: TestClient) -> None:
    create_workspace(client)
    create_article(client)
    client.post("/api/v1/workspaces", json={"name": "Beta Support", "slug": "beta-support"})

    acme_articles = client.get("/api/v1/workspaces/acme-support/knowledge-articles")
    beta_articles = client.get("/api/v1/workspaces/beta-support/knowledge-articles")

    assert len(acme_articles.json()["items"]) == 1
    assert beta_articles.json()["items"] == []


def test_publication_requires_a_safe_status_transition(client: TestClient) -> None:
    create_workspace(client)
    article = create_article(client)
    article_url = f"/api/v1/workspaces/acme-support/knowledge-articles/{article['article_id']}"

    published = client.patch(f"{article_url}/status", json={"status": "published"})
    archived = client.patch(f"{article_url}/status", json={"status": "archived"})
    unsafe_republish = client.patch(f"{article_url}/status", json={"status": "published"})

    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None
    assert archived.json()["status"] == "archived"
    assert unsafe_republish.status_code == 409
