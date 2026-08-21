import re
from dataclasses import dataclass

from app.models.draft_evaluation import DraftQualityDecision
from app.models.ticket import SupportTicket


@dataclass(frozen=True)
class DraftQualityResult:
    decision: DraftQualityDecision
    reason: str


class DraftQualityChecker:
    """Fast, explainable hygiene checks; this is not a substitute for human scoring."""

    _NEXT_STEP_WORDS = (
        "please",
        "confirm",
        "reply",
        "contact",
        "check",
        "try",
        "follow up",
        "we will",
        "we'll",
        "next step",
    )

    @classmethod
    def assess(cls, ticket: SupportTicket, draft: str) -> DraftQualityResult:
        body = draft.strip()
        normalised_body = cls._normalise(body)
        normalised_message = cls._normalise(ticket.message)

        if len(body) < 40:
            return cls._needs_review("The draft is too short to give the customer a useful response.")
        if re.match(r"^(subject|message|customer name|ticket subject)\s*:", body, re.IGNORECASE):
            return cls._needs_review("The draft begins with copied ticket metadata instead of a reply.")
        if len(normalised_message) >= 40 and normalised_message in normalised_body:
            return cls._needs_review("The draft repeats the customer's full message instead of responding to it.")
        if body.startswith(("{", "[", "<")):
            return cls._needs_review("The draft looks like structured prompt data rather than customer-facing prose.")
        if max((len(line) for line in body.splitlines()), default=0) > 600:
            return cls._needs_review("The draft contains an unusually long unbroken line and is hard to scan.")
        if not any(word in normalised_body for word in cls._NEXT_STEP_WORDS):
            return cls._needs_review("The draft has no clear next step for the customer or support team.")
        return DraftQualityResult(
            decision=DraftQualityDecision.PASSED,
            reason="The draft is readable, customer-facing, and includes a clear next step.",
        )

    @staticmethod
    def _normalise(text: str) -> str:
        return re.sub(r"\W+", " ", text.casefold()).strip()

    @staticmethod
    def _needs_review(reason: str) -> DraftQualityResult:
        return DraftQualityResult(
            decision=DraftQualityDecision.NEEDS_HUMAN_REVIEW,
            reason=reason,
        )
