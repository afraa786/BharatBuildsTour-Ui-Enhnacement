"""Payment intent, provider result and signed-event state transitions."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.commercial import CommercialError
from app.core.config import get_settings
from app.db.session import transaction_session
from app.modules.inventory.models import Inventory
from app.modules.payments import repository
from app.modules.payments.models import Payment, PaymentEvent, PaymentOutbox
from app.modules.payments.provider import PaymentLinkProvider, RazorpayProvider
from app.modules.payments.schemas import PaymentLinkIn, PaymentOut, PaymentStatus, WebhookOut
from app.modules.pricing.repository import claim_idempotency

ACTION = "payments.create-link"


def _response(payment: Payment) -> PaymentOut:
    return PaymentOut(
        business_id=payment.business_id,
        run_id=payment.run_id,
        payment_id=payment.id,
        quote_id=payment.quote_id,
        quote_version=payment.quote_version,
        status=PaymentStatus(payment.status),
        amount_paise=payment.amount_paise,
        currency=payment.currency,
        provider_link_id=payment.provider_link_id,
        payment_url=payment.payment_url,
        link_expires_at=payment.link_expires_at,
        reconciliation_hold=payment.reconciliation_hold,
    )


def _fingerprint(request: PaymentLinkIn) -> str:
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{ACTION}:{canonical}".encode()).hexdigest()


def _stock_available(session: Session, business_id: UUID, quote_id: UUID) -> bool:
    # Quote creation never reserves stock. Verify every frozen quantity again.
    required: dict[UUID, Decimal] = {}
    for item in repository.quote_items(session, business_id, quote_id):
        required[item.product_id] = required.get(item.product_id, Decimal(0)) + (
            item.quantity * item.pack_size
        )
    for product_id, quantity in required.items():
        inventory = session.scalar(
            select(Inventory).where(
                Inventory.business_id == business_id, Inventory.product_id == product_id
            )
        )
        if inventory is None or inventory.on_hand_qty < quantity:
            return False
    return True


def create_link(
    business_id: UUID,
    request: PaymentLinkIn,
    idempotency_key: str,
    *,
    provider: PaymentLinkProvider | None = None,
) -> PaymentOut:
    settings = get_settings()
    account_key = settings.razorpay_account_id
    if not account_key:
        raise CommercialError(
            503, "PAYMENT_PROVIDER_UNCONFIGURED", "Payment provider is unavailable."
        )
    if provider is None and (
        not settings.razorpay_key_id or not settings.razorpay_key_secret.get_secret_value()
    ):
        raise CommercialError(
            503, "PAYMENT_PROVIDER_UNCONFIGURED", "Payment provider is unavailable."
        )
    fingerprint = _fingerprint(request)
    with transaction_session() as session:
        key, claimed = claim_idempotency(session, business_id, ACTION, idempotency_key, fingerprint)
        if key.request_sha256 != fingerprint:
            raise CommercialError(409, "IDEMPOTENCY_CONFLICT", "Key was used for another request.")
        if not claimed:
            if key.state == "COMPLETED" and key.response_reference:
                return PaymentOut.model_validate(key.response_reference)
            raise CommercialError(
                409,
                "IDEMPOTENCY_IN_PROGRESS",
                "Payment intent requires provider-reference reconciliation before retry.",
            )
        quote = repository.lock_quote(session, business_id, request.quote_id)
        if quote is None:
            raise CommercialError(404, "NOT_FOUND", "Quote not found.")
        if (
            quote.run_id != request.run_id
            or quote.quote_version != request.quote_version
            or not quote.is_current
        ):
            raise CommercialError(409, "QUOTE_VERSION_MISMATCH", "Quote version is not current.")
        now = datetime.now(UTC)
        if now >= quote.expires_at:
            raise CommercialError(409, "QUOTE_EXPIRED", "Quote has expired.")
        if quote.approval_required and not quote.approval_satisfied:
            raise CommercialError(409, "APPROVAL_REQUIRED", "Quote approval is required.")
        if quote.status != "ACCEPTED" or quote.acceptance_evidence is None:
            raise CommercialError(
                409, "QUOTE_NOT_ACCEPTED", "Quote acceptance evidence is required."
            )
        if quote.currency != "INR" or quote.total_paise <= 0:
            raise CommercialError(409, "PAYMENT_AMOUNT_MISMATCH", "Quote amount is invalid.")
        if request.amount_paise is not None and request.amount_paise != quote.total_paise:
            raise CommercialError(409, "PAYMENT_AMOUNT_MISMATCH", "Amount differs from quote.")
        if repository.active_payment(session, business_id, quote.id) is not None:
            raise CommercialError(
                409, "PAYMENT_ALREADY_EXISTS", "Quote already has a payment intent."
            )
        if not _stock_available(session, business_id, quote.id):
            raise CommercialError(409, "INSUFFICIENT_STOCK", "Stock is insufficient for payment.")
        payment_id = uuid4()
        reference_id = str(payment_id)
        intent_amount_paise = quote.total_paise
        intent_expiry = quote.expires_at
        payment = Payment(
            id=payment_id,
            business_id=business_id,
            run_id=quote.run_id,
            quote_id=quote.id,
            quote_version=quote.quote_version,
            status="CREATED",
            amount_paise=intent_amount_paise,
            currency="INR",
            provider_account_key=account_key,
            provider_reference_id=reference_id,
            link_expires_at=intent_expiry,
        )
        session.add(payment)
        session.flush()

    adapter = provider or RazorpayProvider()
    # Intentionally outside both DB transactions. Unknown outcomes remain CREATED.
    link = adapter.create_link(
        reference_id=reference_id,
        amount_paise=intent_amount_paise,
        expire_by=intent_expiry,
    )
    with transaction_session() as session:
        payment = repository.lock_payment(session, business_id, payment_id)
        assert payment is not None
        if (
            link.reference_id != reference_id
            or link.amount_paise != payment.amount_paise
            or link.currency != "INR"
            or link.status not in {"created", "paid"}
            or not link.link_id
            or not link.short_url
        ):
            # A mismatched provider result needs manual reconciliation; do not issue a URL.
            raise CommercialError(
                409, "PAYMENT_AMOUNT_MISMATCH", "Provider link differs from payment intent."
            )
        if payment.status in {"CREATED", "PAID"}:
            payment.provider_link_id = link.link_id
            payment.payment_url = link.short_url
            if payment.status == "CREATED":
                payment.status = "PENDING"
            payment.updated_at = datetime.now(UTC)
        key, _ = claim_idempotency(session, business_id, ACTION, idempotency_key, fingerprint)
        result = _response(payment)
        key.state = "COMPLETED"
        key.response_status = 200
        key.response_reference = result.model_dump(mode="json")
        return result


def get_payment(session: Session, business_id: UUID, payment_id: UUID) -> PaymentOut:
    payment = repository.lock_payment(session, business_id, payment_id)
    if payment is None:
        raise CommercialError(404, "NOT_FOUND", "Payment not found.")
    return _response(payment)


def _verified_payload(raw_body: bytes, signature: str | None) -> dict:
    settings = get_settings()
    secrets = [
        settings.razorpay_webhook_secret.get_secret_value(),
        settings.razorpay_previous_webhook_secret.get_secret_value(),
    ]
    if not signature or not any(
        hmac.compare_digest(
            hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest(), signature
        )
        for secret in secrets
        if secret
    ):
        raise CommercialError(401, "INVALID_WEBHOOK_SIGNATURE", "Invalid webhook signature.")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CommercialError(422, "VALIDATION_ERROR", "Invalid webhook JSON.") from exc
    if not isinstance(payload, dict):
        raise CommercialError(422, "VALIDATION_ERROR", "Invalid webhook structure.")
    return payload


def process_webhook(raw_body: bytes, signature: str | None, event_id: str | None) -> WebhookOut:
    payload = _verified_payload(raw_body, signature)
    account_key = get_settings().razorpay_account_id
    if not account_key or payload.get("account_id") != account_key:
        raise CommercialError(
            409, "PAYMENT_ACCOUNT_MISMATCH", "Provider account is not recognized."
        )
    if not event_id or len(event_id) > 160:
        raise CommercialError(422, "VALIDATION_ERROR", "Provider event ID is required.")
    if payload.get("event") != "payment_link.paid":
        return WebhookOut()
    try:
        link = payload["payload"]["payment_link"]["entity"]
        provider_payment = payload["payload"]["payment"]["entity"]
        link_id = link["id"]
        provider_payment_id = provider_payment["id"]
        amount = link["amount"]
        amount_paid = link["amount_paid"]
        payment_amount = provider_payment["amount"]
        currency = link["currency"]
        payment_currency = provider_payment["currency"]
        link_status = link["status"]
        payment_status = provider_payment["status"]
    except (KeyError, TypeError) as exc:
        raise CommercialError(422, "VALIDATION_ERROR", "Incomplete provider event.") from exc
    if not isinstance(link_id, str) or not isinstance(provider_payment_id, str):
        raise CommercialError(422, "VALIDATION_ERROR", "Invalid provider identifiers.")
    digest = hashlib.sha256(raw_body).hexdigest()
    with transaction_session() as session:
        payment = repository.lock_provider_payment(session, account_key, link_id)
        if payment is None:
            raise CommercialError(404, "NOT_FOUND", "Provider link is not recognized.")
        prior = repository.get_event(session, account_key, event_id)
        if prior is not None:
            if prior.payload_sha256 != digest:
                raise CommercialError(409, "DUPLICATE_EVENT", "Event ID has conflicting content.")
            return WebhookOut(
                duplicate=True,
                payment_id=payment.id,
                status=PaymentStatus(payment.status),
                reconciliation_hold=payment.reconciliation_hold,
            )
        valid = (
            type(amount) is int
            and type(amount_paid) is int
            and type(payment_amount) is int
            and amount == amount_paid == payment_amount == payment.amount_paise
            and currency == payment_currency == payment.currency
            and link_status == "paid"
            and payment_status == "captured"
            and link.get("reference_id", payment.provider_reference_id)
            == payment.provider_reference_id
        )
        now = datetime.now(UTC)
        event = PaymentEvent(
            business_id=payment.business_id,
            payment_id=payment.id,
            provider="razorpay",
            provider_account_key=account_key,
            provider_event_id=event_id,
            event_type="payment_link.paid",
            payload_sha256=digest,
            safe_metadata={"valid_full_payment": valid},
            verified_at=now,
        )
        session.add(event)
        session.flush()
        if not valid:
            session.add(
                PaymentOutbox(
                    business_id=payment.business_id,
                    payment_event_id=event.id,
                    topic="payment.reconciliation_required",
                    payload={
                        "business_id": str(payment.business_id),
                        "payment_id": str(payment.id),
                        "reason": "SIGNED_PAYMENT_MISMATCH",
                    },
                )
            )
        if (
            valid
            and payment.status == "PAID"
            and provider_payment_id != payment.provider_payment_id
        ):
            payment.reconciliation_hold = True
            session.add(
                PaymentOutbox(
                    business_id=payment.business_id,
                    payment_event_id=event.id,
                    topic="payment.reconciliation_required",
                    payload={
                        "business_id": str(payment.business_id),
                        "payment_id": str(payment.id),
                        "reason": "ADDITIONAL_PROVIDER_PAYMENT",
                    },
                )
            )
        if valid and payment.status != "PAID":
            previous_status = payment.status
            payment.status = "PAID"
            payment.provider_payment_id = provider_payment_id
            payment.provider_order_id = provider_payment.get("order_id")
            try:
                provider_time = datetime.fromtimestamp(payload["created_at"], UTC)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise CommercialError(
                    422, "VALIDATION_ERROR", "Provider event time is invalid."
                ) from exc
            payment.paid_at = provider_time
            quote = repository.lock_quote(session, payment.business_id, payment.quote_id)
            payment.reconciliation_hold = (
                previous_status in {"EXPIRED", "CANCELLED", "FAILED"}
                or provider_time >= payment.link_expires_at
                or quote is None
                or quote.status != "ACCEPTED"
                or not quote.is_current
                or not _stock_available(session, payment.business_id, payment.quote_id)
            )
            payment.updated_at = now
            session.add(
                PaymentOutbox(
                    business_id=payment.business_id,
                    payment_event_id=event.id,
                    topic="payment.verified",
                    payload={
                        "business_id": str(payment.business_id),
                        "run_id": payment.run_id,
                        "payment_id": str(payment.id),
                        "quote_id": str(payment.quote_id),
                        "quote_version": payment.quote_version,
                        "reconciliation_hold": payment.reconciliation_hold,
                    },
                )
            )
        return WebhookOut(
            payment_id=payment.id,
            status=PaymentStatus(payment.status),
            reconciliation_hold=payment.reconciliation_hold,
        )
