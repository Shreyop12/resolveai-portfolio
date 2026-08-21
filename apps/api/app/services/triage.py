import json
import logging
import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from app.models.ticket import SupportTicket
from app.models.triage import TicketTriageAssessment, TriageCategory, TriageDecision
from app.repositories.triage import TicketTriageRepository
from app.services.embeddings import ChatClient, EmbeddingProviderError

logger = logging.getLogger(__name__)


class TriageResult(BaseModel):
    decision: TriageDecision
    category: TriageCategory
    reason: str
    model: str | None = None


class TicketTriageSpecialist:
    """Classifies a ticket into a small, safe workflow decision."""

    agent_name = "ticket_triage_specialist"
    _sensitive_signals = {
        "security breach": "Security incidents require a human support owner.",
        "compromised": "Potential account compromise requires a human support owner.",
        "password reset": "Credential changes require a human support owner.",
        "delete my account": "Account deletion requires a human support owner.",
        "delete our account": "Account deletion requires a human support owner.",
        "delete our company data": "Data-deletion requests require a human support owner.",
        "delete company data": "Data-deletion requests require a human support owner.",
        "permanently delete": "Data-deletion requests require a human support owner.",
        "erase all data": "Data-deletion requests require a human support owner.",
        "refund": "Refund requests require a human support owner.",
        "chargeback": "Payment disputes require a human support owner.",
        "personal data": "Privacy requests require a human support owner.",
        "gdpr": "Privacy requests require a human support owner.",
    }
    def __init__(self, chat_client: ChatClient) -> None:
        self.chat_client = chat_client

    async def assess(self, ticket: SupportTicket) -> TriageResult:
        text = f"{ticket.subject}\n{ticket.message}".lower()
        for signal, reason in self._sensitive_signals.items():
            if signal in text:
                return TriageResult(
                    decision=TriageDecision.HUMAN_ESCALATION,
                    category=self._category_for_sensitive_signal(signal),
                    reason=reason,
                    model="deterministic-safety-rules",
                )
        try:
            response = await self.chat_client.complete(
                system=(
                    "You are the ticket triage specialist in a customer-support workflow. "
                    "Return exactly one JSON object, with no markdown, using keys decision, category, reason. "
                    "decision must be draft_allowed or human_escalation. category must be troubleshooting, "
                    "how_to, account_or_billing, security_or_privacy, or uncertain. "
                    "Use draft_allowed only for routine product troubleshooting or how-to questions. "
                    "Escalate security, privacy, account changes, billing, legal, or unclear requests. "
                    "reason must be a short customer-safe explanation and must not reveal private reasoning."
                ),
                user=(
                    f"Subject: {ticket.subject}\n"
                    f"Customer message: {ticket.message}"
                ),
            )
            result = TriageResult.model_validate(json.loads(self._json_object(response))).model_copy(
                update={"model": self.chat_client.model_name}
            )
        except EmbeddingProviderError as error:
            logger.warning(
                "Triage provider failed; using safe fallback. provider_error=%s",
                error,
            )
            return self._safe_fallback()
        except (ValidationError, json.JSONDecodeError) as error:
            logger.warning(
                "Triage response was invalid; using safe fallback. error_type=%s",
                type(error).__name__,
            )
            return self._safe_fallback()
        if result.decision == TriageDecision.DRAFT_ALLOWED and result.category in {
            TriageCategory.TROUBLESHOOTING,
            TriageCategory.HOW_TO,
        }:
            return result
        return TriageResult(
            decision=TriageDecision.HUMAN_ESCALATION,
            category=result.category,
            reason="This request needs a human support owner before any reply is drafted.",
            model=result.model,
        )

    @staticmethod
    def _json_object(response: str) -> str:
        match = re.search(r"\{.*\}", response, flags=re.DOTALL)
        return match.group(0) if match else response

    @staticmethod
    def _category_for_sensitive_signal(signal: str) -> TriageCategory:
        if signal in {"refund", "chargeback"}:
            return TriageCategory.ACCOUNT_OR_BILLING
        return TriageCategory.SECURITY_OR_PRIVACY

    @staticmethod
    def _safe_fallback() -> TriageResult:
        return TriageResult(
            decision=TriageDecision.HUMAN_ESCALATION,
            category=TriageCategory.UNCERTAIN,
            reason="ResolveAI could not classify this request safely, so a human support owner must review it.",
            model="safe-fallback",
        )


class TicketTriageService:
    def __init__(self, repository: TicketTriageRepository, specialist: TicketTriageSpecialist) -> None:
        self.repository = repository
        self.specialist = specialist

    async def assess(self, ticket: SupportTicket) -> TicketTriageAssessment:
        result = await self.specialist.assess(ticket)
        year = datetime.now(UTC).year
        return await self.repository.create(
            TicketTriageAssessment(
                assessment_id=f"TRI-{year}-{uuid.uuid4().hex[:8].upper()}",
                ticket_id=ticket.id,
                decision=result.decision,
                category=result.category,
                reason=result.reason[:500],
                agent_name=self.specialist.agent_name,
                model=result.model or self.specialist.chat_client.model_name,
            )
        )
