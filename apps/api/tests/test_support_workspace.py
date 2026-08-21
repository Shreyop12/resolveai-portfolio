import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.embedding import EMBEDDING_DIMENSIONS
from app.services.embeddings import (
    get_draft_chat_client,
    get_embedding_client,
    get_ollama_draft_chat_client,
    get_openrouter_draft_chat_client,
    get_reviewer_chat_client,
    get_triage_chat_client,
)
from app.services.draft_evaluation_dispatcher import get_draft_evaluation_dispatcher


class FakeEmbeddingClient:
    """Deterministic stand-in; real semantic quality is verified against Ollama."""

    model_name = "test-embedding-model"

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        normalized = text.lower()
        if any(term in normalized for term in ("sso", "saml", "login", "sign in")):
            vector[0] = 1.0
        elif any(term in normalized for term in ("billing", "invoice", "payment")):
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector


class FakeChatClient:
    model_name = "test-chat-model"

    async def complete(self, *, system: str, user: str) -> str:
        if "ticket triage specialist" in system:
            return '{"decision":"draft_allowed","category":"troubleshooting","reason":"Routine product troubleshooting can continue to source retrieval."}'
        if "grounding reviewer" in system:
            return '{"decision":"grounded","reason":"The proposed reply stays within the approved SSO guidance."}'
        assert "approved-source-packet" in user.lower()
        return "Thanks for reaching out. Please verify the SAML metadata and domain settings, then try signing in again."


class FakeDraftEvaluationDispatcher:
    def __init__(self) -> None:
        self.job_ids: list[str] = []

    async def dispatch(self, job_id: str) -> None:
        self.job_ids.append(job_id)


@pytest.fixture()
def client() -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def initialize() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    asyncio.run(initialize())
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_embedding_client] = FakeEmbeddingClient
    app.dependency_overrides[get_draft_chat_client] = FakeChatClient
    app.dependency_overrides[get_reviewer_chat_client] = FakeChatClient
    app.dependency_overrides[get_triage_chat_client] = FakeChatClient
    app.dependency_overrides[get_ollama_draft_chat_client] = FakeChatClient
    app.dependency_overrides[get_openrouter_draft_chat_client] = FakeChatClient
    app.dependency_overrides[get_draft_evaluation_dispatcher] = FakeDraftEvaluationDispatcher
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def create_workspace(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces", json={"name": "Acme Support", "slug": "acme-support"}
    )
    assert response.status_code == 201
    return response.json()


def create_ticket(client: TestClient, workspace_slug: str = "acme-support") -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_slug}/tickets",
        json={
            "customer_name": "Maya Chen",
            "customer_email": "maya@example.com",
            "subject": "Cannot sign in with SSO",
            "message": "Our team receives an access denied message when using company login.",
            "priority": "high",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_workspace_and_ticket(client: TestClient) -> None:
    workspace = create_workspace(client)
    ticket = create_ticket(client)

    assert workspace["slug"] == "acme-support"
    assert ticket["ticket_id"].startswith("TKT-2026-")
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"


def test_lists_workspace_tickets_and_keeps_workspaces_isolated(client: TestClient) -> None:
    create_workspace(client)
    create_ticket(client)
    client.post("/api/v1/workspaces", json={"name": "Beta Support", "slug": "beta-support"})

    acme_tickets = client.get("/api/v1/workspaces/acme-support/tickets")
    beta_tickets = client.get("/api/v1/workspaces/beta-support/tickets")

    assert len(acme_tickets.json()["items"]) == 1
    assert beta_tickets.json()["items"] == []


def test_ticket_note_and_valid_transition(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)
    ticket_url = f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}"

    note = client.post(f"{ticket_url}/notes", json={"body": "Customer uses enterprise SSO."})
    transition = client.patch(f"{ticket_url}/status", json={"status": "drafting"})
    detail = client.get(ticket_url)

    assert note.status_code == 201
    assert transition.json()["status"] == "drafting"
    assert detail.json()["notes"][0]["body"] == "Customer uses enterprise SSO."


def test_invalid_ticket_transition_is_rejected(client: TestClient) -> None:
    create_workspace(client)
    ticket = create_ticket(client)

    response = client.patch(
        f"/api/v1/workspaces/acme-support/tickets/{ticket['ticket_id']}/status",
        json={"status": "awaiting_review"},
    )

    assert response.status_code == 409
    assert "Cannot transition" in response.json()["detail"]
