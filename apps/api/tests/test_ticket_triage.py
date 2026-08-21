from fastapi.testclient import TestClient

from tests.test_knowledge_base import create_article
from tests.test_support_workspace import client, create_ticket, create_workspace  # noqa: F401


def test_routine_ticket_is_allowed_to_continue_to_the_coordinator(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)

    assessment = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )
    stored = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )

    assert assessment.status_code == 200
    assert assessment.json()["decision"] == "draft_allowed"
    assert assessment.json()["category"] == "troubleshooting"
    assert stored.json()["assessment_id"] == assessment.json()["assessment_id"]


def test_sensitive_ticket_escalates_without_creating_a_draft(client: TestClient) -> None:
    create_workspace(client)
    ticket = client.post(
        "/api/v1/workspaces/acme-support/tickets",
        json={
            "customer_name": "Ari Shah",
            "customer_email": "ari@example.com",
            "subject": "Requesting a refund",
            "message": "Please refund our subscription because the charge is incorrect.",
            "priority": "high",
        },
    ).json()
    article = create_article(client)
    client.patch(
        f"/api/v1/workspaces/acme-support/knowledge-articles/{article['article_id']}/status",
        json={"status": "published"},
    )

    assessment = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )
    draft = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/drafts/generate"
    )

    assert assessment.status_code == 200
    assert assessment.json()["decision"] == "human_escalation"
    assert assessment.json()["category"] == "account_or_billing"
    assert draft.status_code == 422
    assert "escalated to a human" in draft.json()["detail"]


def test_data_deletion_language_uses_fast_deterministic_escalation(client: TestClient) -> None:
    create_workspace(client)
    ticket = client.post(
        "/api/v1/workspaces/acme-support/tickets",
        json={
            "customer_name": "Daniel Ortiz",
            "customer_email": "daniel@example.com",
            "subject": "Please delete our company data",
            "message": "Please permanently delete all customer records, backups, and user accounts.",
            "priority": "urgent",
        },
    ).json()

    assessment = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )

    assert assessment.status_code == 200
    assert assessment.json()["decision"] == "human_escalation"
    assert assessment.json()["model"] == "deterministic-safety-rules"


def test_routine_sso_troubleshooting_skips_the_model_and_allows_grounded_drafting(
    client: TestClient,
) -> None:
    create_workspace(client)
    ticket = client.post(
        "/api/v1/workspaces/acme-support/tickets",
        json={
            "customer_name": "Jordan Lee",
            "customer_email": "jordan@example.com",
            "subject": "Company SSO access denied",
            "message": "Our identity provider certificate changed and employees now receive access denied.",
            "priority": "normal",
        },
    ).json()

    assessment = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )

    assert assessment.status_code == 200
    assert assessment.json()["decision"] == "draft_allowed"
    assert assessment.json()["category"] == "troubleshooting"
    assert assessment.json()["model"] == "deterministic-routine-rules"


def test_a_new_assessment_replaces_the_visible_latest_decision(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)

    first = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )
    second = client.post(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )
    latest = client.get(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/triage"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert latest.json()["assessment_id"] == second.json()["assessment_id"]
