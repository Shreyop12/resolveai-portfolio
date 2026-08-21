import asyncio

import pytest

from app.models.ticket import SupportTicket, TicketPriority
from app.services.draft_coordinator import GroundedDraftWriter
from app.services.embeddings import EmbeddingProviderError


def ticket() -> SupportTicket:
    return SupportTicket(
        ticket_id="TKT-TEST",
        workspace_id="00000000-0000-0000-0000-000000000001",
        customer_name="Ray",
        customer_email="ray@example.com",
        subject="Delete company data",
        message="Please permanently delete our workspace and all company data today.",
        priority=TicketPriority.NORMAL,
    )


class CapturingChatClient:
    model_name = "test-model"

    def __init__(self, response: str) -> None:
        self.response = response
        self.system = ""
        self.user = ""

    async def complete(self, *, system: str, user: str) -> str:
        self.system = system
        self.user = user
        return self.response


def test_writer_uses_structured_ticket_data_and_returns_a_customer_reply() -> None:
    client = CapturingChatClient("Hello Ray,\n\nWe will route this deletion request to the account team.")

    draft = asyncio.run(
        GroundedDraftWriter(client).write(
            ticket(), [("KB-1", "Account deletion", "Escalate deletion requests to the account team.")]
        )
    )

    assert draft.startswith("Hello Ray")
    assert "<customer-ticket-json>" in client.user
    assert '"title": "Delete company data"' in client.user
    assert "Subject:" not in client.user
    assert "Message:" not in client.user


@pytest.mark.parametrize(
    "copied_draft",
    [
        "Subject: Delete company data\nMessage: Please permanently delete our workspace and all company data today.",
        "Hello. Please permanently delete our workspace and all company data today.",
    ],
)
def test_writer_rejects_copied_ticket_content(copied_draft: str) -> None:
    client = CapturingChatClient(copied_draft)

    with pytest.raises(EmbeddingProviderError, match="rejected"):
        asyncio.run(
            GroundedDraftWriter(client).write(
                ticket(), [("KB-1", "Account deletion", "Escalate deletion requests.")]
            )
        )
