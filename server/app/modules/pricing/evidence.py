"""Narrow trusted-Rehbar evidence application boundary; no public route."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.commercial import CommercialError
from app.modules.pricing import repository
from app.modules.pricing.schemas import QuoteStatus


class ApprovalEvidence(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1)
    quote_id: UUID
    quote_version: int = Field(gt=0)
    approval_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    decision: str
    decided_at: datetime
    expires_at: datetime | None = None
    revoked: bool = False


class AcceptanceEvidence(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1)
    quote_id: UUID
    quote_version: int = Field(gt=0)
    acceptance_id: str = Field(min_length=1)
    buyer_whatsapp_e164: str = Field(min_length=1)
    source_message_id: str = Field(min_length=1)
    channel: str
    accepted_at: datetime


def _current_quote(session: Session, business_id: UUID, run_id: str, quote_id: UUID, version: int):
    quote = repository.get_quote_locked(session, business_id, quote_id)
    if quote is None:
        raise CommercialError(404, "NOT_FOUND", "Quote not found.")
    if quote.run_id != run_id or quote.quote_version != version or not quote.is_current:
        raise CommercialError(
            409, "QUOTE_VERSION_MISMATCH", "The quote version is no longer current."
        )
    if datetime.now(UTC) >= quote.expires_at:
        raise CommercialError(409, "QUOTE_EXPIRED", "The quote has expired.")
    return quote


def apply_approval(
    session: Session, evidence: ApprovalEvidence, *, authorized_actor_ids: set[str]
) -> None:
    """Caller must authenticate Rehbar before invoking this internal function."""
    quote = _current_quote(
        session, evidence.business_id, evidence.run_id, evidence.quote_id, evidence.quote_version
    )
    if evidence.actor_id not in authorized_actor_ids:
        raise CommercialError(403, "APPROVAL_REQUIRED", "Approving actor is not authorized.")
    if evidence.action != "approve_quote":
        raise CommercialError(409, "APPROVAL_REQUIRED", "Approval action does not match the quote.")
    if quote.status == QuoteStatus.GENERATED and quote.approval_id == evidence.approval_id:
        if quote.approval_evidence != evidence.model_dump(mode="json"):
            raise CommercialError(
                409, "EVIDENCE_CONFLICT", "Approval evidence conflicts with its ID."
            )
        return
    if quote.status != QuoteStatus.DRAFT or not quote.approval_required:
        raise CommercialError(
            409, "APPROVAL_REQUIRED", "This quote cannot accept approval evidence."
        )
    if evidence.actor_id not in authorized_actor_ids:
        raise CommercialError(403, "APPROVAL_REQUIRED", "Approving actor is not authorized.")
    if evidence.decision != "approved" or evidence.revoked:
        raise CommercialError(409, "APPROVAL_REQUIRED", "Approval evidence is not valid.")
    if evidence.decided_at.tzinfo is None or evidence.decided_at > datetime.now(UTC):
        raise CommercialError(409, "APPROVAL_REQUIRED", "Approval timestamp is invalid.")
    if evidence.expires_at is not None:
        if evidence.expires_at.tzinfo is None or evidence.expires_at <= datetime.now(UTC):
            raise CommercialError(409, "APPROVAL_REQUIRED", "Approval has expired.")

    quote.approval_id = evidence.approval_id
    quote.approval_evidence = evidence.model_dump(mode="json")
    quote.approval_satisfied = True
    quote.generated_at = datetime.now(UTC)
    quote.status = QuoteStatus.GENERATED
    session.flush()


def apply_acceptance(session: Session, evidence: AcceptanceEvidence) -> None:
    """Caller must authenticate Rehbar and its source message before invoking."""
    quote = _current_quote(
        session, evidence.business_id, evidence.run_id, evidence.quote_id, evidence.quote_version
    )
    if evidence.channel != "whatsapp":
        raise CommercialError(422, "VALIDATION_ERROR", "Acceptance channel is not enabled.")
    if evidence.buyer_whatsapp_e164 != quote.buyer_snapshot.get("whatsapp_e164"):
        raise CommercialError(403, "UNAUTHORIZED", "Buyer identity does not match the quote.")
    if quote.status == QuoteStatus.ACCEPTED and quote.acceptance_id == evidence.acceptance_id:
        if quote.acceptance_evidence != evidence.model_dump(mode="json"):
            raise CommercialError(
                409, "EVIDENCE_CONFLICT", "Acceptance evidence conflicts with its ID."
            )
        return
    if quote.status != QuoteStatus.GENERATED:
        raise CommercialError(409, "QUOTE_VERSION_MISMATCH", "Quote is not ready for acceptance.")
    if evidence.channel != "whatsapp":
        raise CommercialError(422, "VALIDATION_ERROR", "Acceptance channel is not enabled.")
    if evidence.buyer_whatsapp_e164 != quote.buyer_snapshot.get("whatsapp_e164"):
        raise CommercialError(403, "UNAUTHORIZED", "Buyer identity does not match the quote.")
    if evidence.accepted_at.tzinfo is None or evidence.accepted_at > datetime.now(UTC):
        raise CommercialError(422, "VALIDATION_ERROR", "Acceptance timestamp is invalid.")
    if quote.generated_at is None or evidence.accepted_at < quote.generated_at:
        raise CommercialError(422, "VALIDATION_ERROR", "Acceptance predates quote issuance.")
    if evidence.accepted_at >= quote.expires_at:
        raise CommercialError(409, "QUOTE_EXPIRED", "Acceptance occurred after quote expiry.")

    quote.acceptance_id = evidence.acceptance_id
    quote.acceptance_evidence = evidence.model_dump(mode="json")
    quote.accepted_at = evidence.accepted_at
    quote.status = QuoteStatus.ACCEPTED
    session.flush()
