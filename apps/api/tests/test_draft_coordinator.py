from fastapi.testclient import TestClient

from app.main import app
from app.services.embeddings import (
    get_draft_chat_client,
    get_reviewer_chat_client,
    get_triage_chat_client,
)
from app.services.embeddings import extract_customer_facing_content
from tests.test_knowledge_base import create_article
from tests.test_support_workspace import client, create_ticket, create_workspace  # noqa: F401


def publish_source(client: TestClient, article_id: str) -> None:
    response = client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{article_id}/status",
        json={"status": "published"},
    )
    assert response.status_code == 200


def assess_ticket(client: TestClient, ticket_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket_id}/triage"
    )
    assert response.status_code == 200
    return response.json()


def test_coordinator_creates_source_backed_draft_for_human_review(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)
    article = create_article(client)
    publish_source(client, article["article_id"])
    assessment = assess_ticket(client, ticket["ticket_id"])

    draft = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    )
    ticket_detail = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}"
    )
    runs = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/runs"
    )

    assert draft.status_code == 201
    assert draft.json()["status"] == "awaiting_review"
    assert assessment["decision"] == "draft_allowed"
    assert draft.json()["source_article_ids"] == [article["article_id"]]
    assert draft.json()["coordinator_trace"] == [
        "ticket_triage_specialist",
        "hybrid_retrieval",
        "grounded_draft_writer",
        "grounding_reviewer",
    ]
    assert "SAML metadata" in draft.json()["body"]
    assert ticket_detail.json()["status"] == "awaiting_review"
    assert runs.status_code == 200
    assert runs.json()[0]["status"] == "completed"
    assert runs.json()[0]["source_article_ids"] == [article["article_id"]]
    assert runs.json()[0]["agent_models"] == {
        "ticket_triage_specialist": "test-chat-model",
        "hybrid_retrieval_embedding": "test-embedding-model",
        "grounded_draft_writer": "test-chat-model",
        "grounding_reviewer": "test-chat-model",
    }
    assert [stage["name"] for stage in runs.json()[0]["stages"]] == [
        "ticket_triage_specialist",
        "hybrid_retrieval",
        "grounded_draft_writer",
        "grounding_reviewer",
    ]
    safe_run_text = str(runs.json()[0])
    assert ticket["message"] not in safe_run_text
    assert "private model reasoning" not in safe_run_text
    review = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/grounding-review"
    )
    assert review.status_code == 200
    assert review.json()["decision"] == "grounded"
    assert review.json()["source_article_ids"] == [article["article_id"]]


def test_approval_resolves_ticket_and_rejection_returns_to_drafting(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)
    article = create_article(client)
    publish_source(client, article["article_id"])
    assess_ticket(client, ticket["ticket_id"])
    generated = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    ).json()

    approved = client.patch(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/{generated['draft_id']}/review",
        json={"status": "approved"},
    )
    ticket_detail = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}"
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert ticket_detail.json()["status"] == "resolved"


def test_coordinator_refuses_to_draft_without_an_approved_source(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)
    assess_ticket(client, ticket["ticket_id"])

    response = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    )
    ticket_detail = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}"
    )

    assert response.status_code == 422
    assert "No approved knowledge sources" in response.json()["detail"]
    assert ticket_detail.json()["status"] == "open"
    runs = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/runs"
    )
    assert runs.json()[0]["status"] == "blocked"


def test_coordinator_refuses_a_weak_semantic_only_match(client: TestClient) -> None:
    create_workspace(client)
    ticket = client.post(
        "/api/v1/workspaces/acme-support/tickets",
        json={
            "customer_name": "Jordan Lee",
            "customer_email": "jordan@example.com",
            "subject": "Dashboard never finishes loading",
            "message": "The dashboard stays on a loading spinner after we cleared the browser cache.",
            "priority": "high",
        },
    ).json()
    article = create_article(client)
    publish_source(client, article["article_id"])
    assess_ticket(client, ticket["ticket_id"])

    response = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    )

    assert response.status_code == 422
    assert "No approved knowledge sources match" in response.json()["detail"]


def test_coordinator_requires_a_triage_assessment_before_drafting(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)
    article = create_article(client)
    publish_source(client, article["article_id"])

    response = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    )

    assert response.status_code == 422
    assert "triage specialist" in response.json()["detail"]


def test_model_thinking_is_removed_before_a_draft_can_be_stored() -> None:
    raw_response = "<think>private model reasoning</think>\nHi Maya, please verify your SAML metadata."

    assert extract_customer_facing_content(raw_response) == "Hi Maya, please verify your SAML metadata."


class RejectingReviewChatClient:
    model_name = "test-reviewer-model"

    async def complete(self, *, system: str, user: str) -> str:
        if "ticket triage specialist" in system:
            return '{"decision":"draft_allowed","category":"troubleshooting","reason":"Routine troubleshooting."}'
        if "grounding reviewer" in system:
            return '{"decision":"needs_human_review","reason":"The reply includes an unsupported promise."}'
        return "Please verify the SAML metadata and domain settings before trying to sign in again."


def test_unsupported_draft_is_blocked_before_it_can_be_saved(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)
    article = create_article(client)
    publish_source(client, article["article_id"])
    app.dependency_overrides[get_draft_chat_client] = RejectingReviewChatClient
    app.dependency_overrides[get_reviewer_chat_client] = RejectingReviewChatClient
    app.dependency_overrides[get_triage_chat_client] = RejectingReviewChatClient
    assess_ticket(client, ticket["ticket_id"])

    response = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    )
    drafts = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts"
    )
    review = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/grounding-review"
    )
    ticket_detail = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}"
    )

    assert response.status_code == 422
    assert "grounding reviewer could not verify" in response.json()["detail"]
    assert drafts.json() == []
    assert review.json()["decision"] == "needs_human_review"
    assert ticket_detail.json()["status"] == "open"
