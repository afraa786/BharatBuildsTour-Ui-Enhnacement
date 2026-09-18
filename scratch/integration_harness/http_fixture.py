"""Harness-only PostgreSQL fixture helpers; never a Rehbar transport substitute."""

from datetime import UTC, datetime
from time import sleep
from uuid import UUID

from app.api.commercial import CommercialError
from app.db.session import transaction_session
from app.modules.identity.models import Business, Buyer
from app.modules.payments.models import Payment, PaymentEvent, PaymentOutbox
from app.modules.pricing.evidence import (
    AcceptanceEvidence,
    ApprovalEvidence,
    apply_acceptance,
    apply_approval,
)
from app.seed import DEMO_BUSINESS_ID, seed_demo
from sqlalchemy import func, select, update

BUYER_PHONE = "+919876543210"


def prepare_demo_state(business_id: UUID, buyer_id: UUID) -> None:
    if business_id != DEMO_BUSINESS_ID:
        raise RuntimeError(
            "Harness fixture injection is restricted to the demo business"
        )
    with transaction_session() as session:
        seed_demo(session)
        session.execute(
            update(Business)
            .where(Business.id == business_id)
            .values(
                legal_name="StockAware HTTP Acceptance Seller",
                billing_address="Synthetic Seller Address",
                approval_required_for_all=True,
            )
        )
        buyer = session.get(Buyer, buyer_id)
        if buyer is None:
            session.add(
                Buyer(
                    id=buyer_id,
                    business_id=business_id,
                    display_name="HTTP Acceptance Buyer",
                    whatsapp_e164=BUYER_PHONE,
                    legal_name="HTTP Acceptance Buyer Legal",
                    billing_address="Synthetic Buyer Address",
                )
            )
        elif buyer.business_id != business_id:
            raise RuntimeError("Configured buyer belongs to another business")
        else:
            buyer.display_name = "HTTP Acceptance Buyer"
            buyer.whatsapp_e164 = BUYER_PHONE
            buyer.legal_name = "HTTP Acceptance Buyer Legal"
            buyer.billing_address = "Synthetic Buyer Address"


def inject_rehbar_evidence(
    business_id: UUID, run_id: str, quote_id: UUID, quote_version: int
) -> None:
    # The HTTP response and a yield-dependency commit can become visible on
    # adjacent scheduler ticks. Retry only a not-yet-visible quote, never a
    # domain rejection from the evidence helpers.
    for attempt in range(20):
        now = datetime.now(UTC)
        try:
            with transaction_session() as session:
                apply_approval(
                    session,
                    ApprovalEvidence(
                        business_id=business_id,
                        run_id=run_id,
                        quote_id=quote_id,
                        quote_version=quote_version,
                        approval_id=f"fixture-approval-{quote_id}",
                        action_id=f"fixture-action-{quote_id}",
                        action="approve_quote",
                        actor_id="http-acceptance-owner",
                        decision="approved",
                        decided_at=now,
                    ),
                    authorized_actor_ids={"http-acceptance-owner"},
                )
                apply_acceptance(
                    session,
                    AcceptanceEvidence(
                        business_id=business_id,
                        run_id=run_id,
                        quote_id=quote_id,
                        quote_version=quote_version,
                        acceptance_id=f"fixture-acceptance-{quote_id}",
                        buyer_whatsapp_e164=BUYER_PHONE,
                        source_message_id=f"fixture-message-{quote_id}",
                        channel="whatsapp",
                        accepted_at=datetime.now(UTC),
                    ),
                )
            return
        except CommercialError as error:
            if error.code != "NOT_FOUND" or attempt == 19:
                raise
            sleep(0.05)


def payment_evidence(business_id: UUID, payment_id: UUID) -> dict:
    with transaction_session() as session:
        payment = session.scalar(
            select(Payment).where(
                Payment.business_id == business_id, Payment.id == payment_id
            )
        )
        if payment is None:
            raise RuntimeError("HTTP acceptance payment was not persisted")
        return {
            "payment_id": str(payment.id),
            "provider_reference_id": payment.provider_reference_id,
            "provider_link_id": payment.provider_link_id,
            "status": payment.status,
        }


def outbox_evidence(business_id: UUID, payment_id: UUID) -> dict[str, int]:
    with transaction_session() as session:
        events = session.scalar(
            select(func.count())
            .select_from(PaymentEvent)
            .where(
                PaymentEvent.business_id == business_id,
                PaymentEvent.payment_id == payment_id,
            )
        )
        outbox = session.scalar(
            select(func.count())
            .select_from(PaymentOutbox)
            .join(PaymentEvent, PaymentEvent.id == PaymentOutbox.payment_event_id)
            .where(
                PaymentOutbox.business_id == business_id,
                PaymentEvent.payment_id == payment_id,
                PaymentOutbox.topic == "payment.verified",
            )
        )
        return {"events": events or 0, "verified_outbox": outbox or 0}
