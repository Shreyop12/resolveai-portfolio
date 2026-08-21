import json
import re

from pydantic import BaseModel, ValidationError

from app.models.grounding_review import GroundingReviewDecision
from app.models.ticket import SupportTicket
from app.services.embeddings import ChatClient, EmbeddingProviderError


class GroundingReviewResult(BaseModel):
    decision: GroundingReviewDecision
    reason: str


class GroundingReviewer:
    """Critic specialist that may only validate a draft against the supplied sources."""

    agent_name = "grounding_reviewer"

    def __init__(self, chat_client: ChatClient) -> None:
        self.chat_client = chat_client

    async def review(
        self, ticket: SupportTicket, body: str, sources: list[tuple[str, str, str]]
    ) -> GroundingReviewResult:
        source_packet = "\n\n".join(
            f"[{article_id}] {title}\n{source_body}"
            for article_id, title, source_body in sources
        )
        try:
            response = await self.chat_client.complete(
                system=(
                    "You are the grounding reviewer in a customer-support workflow. "
                    "Check whether every factual instruction or promise in the proposed reply is supported "
                    "by the supplied approved sources. Return exactly one JSON object, with no markdown, "
                    "using keys decision and reason. decision must be grounded or needs_human_review. "
                    "Use grounded only when the reply stays within the sources; otherwise choose "
                    "needs_human_review. reason must be a short safe explanation and never reveal private reasoning."
                ),
                user=(
                    f"Ticket subject: {ticket.subject}\n"
                    f"Proposed reply:\n{body}\n\n"
                    f"Approved sources:\n{source_packet}"
                ),
            )
            result = GroundingReviewResult.model_validate(json.loads(self._json_object(response)))
        except (EmbeddingProviderError, ValidationError, json.JSONDecodeError):
            return self._safe_fallback()
        if result.decision == GroundingReviewDecision.GROUNDED:
            return result
        return GroundingReviewResult(
            decision=GroundingReviewDecision.NEEDS_HUMAN_REVIEW,
            reason="The proposed reply needs a human support owner to verify it against the approved guidance.",
        )

    @staticmethod
    def _json_object(response: str) -> str:
        match = re.search(r"\{.*\}", response, flags=re.DOTALL)
        return match.group(0) if match else response

    @staticmethod
    def _safe_fallback() -> GroundingReviewResult:
        return GroundingReviewResult(
            decision=GroundingReviewDecision.NEEDS_HUMAN_REVIEW,
            reason="ResolveAI could not verify the proposed reply safely, so a human support owner must review it.",
        )
