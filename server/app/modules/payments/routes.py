from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request

from app.api.business_context import AuthorizedBusinessId, enforce_business_claim
from app.api.commercial import CommercialError, CommercialRoute
from app.db.session import transaction_session
from app.modules.payments import service
from app.modules.payments.schemas import PaymentLinkIn, PaymentOut, WebhookOut

router = APIRouter(tags=["payments"], route_class=CommercialRoute)


@router.post("/payments/create-link", response_model=PaymentOut)
def create_link(
    body: PaymentLinkIn,
    business_id: AuthorizedBusinessId,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PaymentOut:
    enforce_business_claim(body.business_id, business_id)
    if idempotency_key is None or not idempotency_key.strip() or len(idempotency_key) > 255:
        raise CommercialError(422, "VALIDATION_ERROR", "A valid Idempotency-Key is required.")
    return service.create_link(business_id, body, idempotency_key)


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: UUID, business_id: AuthorizedBusinessId) -> PaymentOut:
    with transaction_session() as session:
        return service.get_payment(session, business_id, payment_id)


@router.post("/payments/webhook", response_model=WebhookOut)
async def payment_webhook(
    request: Request,
    signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
    event_id: Annotated[str | None, Header(alias="x-razorpay-event-id")] = None,
) -> WebhookOut:
    return service.process_webhook(await request.body(), signature, event_id)
