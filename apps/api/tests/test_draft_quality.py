import uuid

import pytest

from app.models.draft_evaluation import DraftQualityDecision
from app.models.ticket import SupportTicket, TicketPriority
from app.services.draft_quality import DraftQualityChecker


@pytest.fixture
def ticket() -> SupportTicket:
    return SupportTicket(
        ticket_id="TKT-QUALITY",
        workspace_id=uuid.uuid4(),
        customer_name="Ray",
        customer_email="ray@example.com",
        subject="Delete company data",
        message="Please permanently delete our workspace and all company data today.",
        priority=TicketPriority.NORMAL,
    )


def test_quality_checker_passes_a_readable_reply_with_a_next_step(ticket: SupportTicket) -> None:
    result = DraftQualityChecker.assess(
        ticket,
        "Hello Ray,\n\nWe will route this request to the account team. Please confirm that you want us to proceed.",
    )

    assert result.decision == DraftQualityDecision.PASSED


@pytest.mark.parametrize(
    ("draft", "reason_fragment"),
    [
        ("Subject: Delete company data\nMessage: Please permanently delete our workspace and all company data today.", "metadata"),
        ("Hello. Please permanently delete our workspace and all company data today.", "repeats"),
        ("Hello Ray, we received your request and are reviewing it.", "next step"),
    ],
)
def test_quality_checker_flags_unusable_replies(
    ticket: SupportTicket, draft: str, reason_fragment: str
) -> None:
    result = DraftQualityChecker.assess(ticket, draft)

    assert result.decision == DraftQualityDecision.NEEDS_HUMAN_REVIEW
    assert reason_fragment in result.reason
