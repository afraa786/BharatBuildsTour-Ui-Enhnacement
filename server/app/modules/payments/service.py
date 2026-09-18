import hmac
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import Buyer
from app.modules.invoices.models import Invoice, InvoiceSequence
from app.modules.invoices.service import (
    InvoiceDraft,
    generate_invoice_pdf_artifact,
    next_invoice_number,
)
from app.modules.payments.models import Payment, PaymentEvent, PaymentOutbox
from app.modules.pricing.models import Quote, QuoteItem

RAZORPAY_PAYMENT_LINKS_URL = "https://api.razorpay.com/v1/payment_links"


class RazorpayPaymentLinkRequest(BaseModel):
    run_id: str = Field(min_length=1)
    quote_id: str = Field(min_length=1)
    amount_paise: int = Field(gt=0)
    buyer_name: str = Field(min_length=1)
    buyer_phone: str = Field(min_length=5)
    description: str | None = None
    callback_url: str | None = None
    expires_at: datetime | None = None


class RazorpayPaymentLinkResult(BaseModel):
    provider_link_id: str
    payment_url: str
    status: str
    reference_id: str
    amount_paise: int
    currency: str


class CapturedPaymentEvent(BaseModel):
    provider_event_id: str
    provider_payment_id: str
    provider_order_id: str | None = None
    amount_paise: int
    currency: str
    run_id: str
    quote_id: str
    paid_at: datetime
    provider_link_id: str | None = None
    event_type: str


class WebhookProcessingResult(BaseModel):
    accepted: bool = True
    provider_event_id: str
    provider_payment_id: str | None = None
    run_id: str | None = None
    quote_id: str | None = None
    payment_id: str | None = None
    payment_status: str | None = None
    invoice_id: str | None = None
    invoice_number: str | None = None
    invoice_artifact_key: str | None = None
    idempotent: bool = False
    quarantined: bool = False
    reason: str | None = None


def verify_razorpay_signature(raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    expected = hmac.new(webhook_secret.encode(), raw_body, sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def build_payment_link_payload(request: RazorpayPaymentLinkRequest) -> dict[str, Any]:
    reference_id = f"{request.run_id}:{request.quote_id}"
    payload: dict[str, Any] = {
        "amount": request.amount_paise,
        "currency": "INR",
        "reference_id": reference_id,
        "description": request.description or f"StockAware quote {request.run_id}",
        "customer": {
            "name": request.buyer_name,
            "contact": request.buyer_phone,
        },
        "notify": {"sms": False, "email": False},
        "notes": {"run_id": request.run_id, "quote_id": request.quote_id},
    }
    if request.callback_url:
        payload["callback_url"] = request.callback_url
        payload["callback_method"] = "get"
    if request.expires_at:
        payload["expire_by"] = int(request.expires_at.timestamp())
    return payload


async def create_payment_link(
    *,
    client: httpx.AsyncClient,
    request: RazorpayPaymentLinkRequest,
    key_id: str,
    key_secret: str,
) -> RazorpayPaymentLinkResult:
    response = await client.post(
        RAZORPAY_PAYMENT_LINKS_URL,
        json=build_payment_link_payload(request),
        auth=(key_id, key_secret),
    )
    response.raise_for_status()
    payload = response.json()
    return RazorpayPaymentLinkResult(
        provider_link_id=payload["id"],
        payment_url=payload["short_url"],
        status=payload["status"],
        reference_id=payload["reference_id"],
        amount_paise=payload["amount"],
        currency=payload["currency"],
    )


def parse_captured_payment_event(event: dict[str, Any]) -> CapturedPaymentEvent:
    event_type = event.get("event")
    if event_type not in {"payment.captured", "payment_link.paid"}:
        raise ValueError("Razorpay event is not captured")
    entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    if entity.get("captured") is not True and entity.get("status") != "captured":
        raise ValueError("Razorpay payment is not captured")
    if entity.get("currency") != "INR":
        raise ValueError("Razorpay payment currency must be INR")
    notes = entity.get("notes") or {}
    run_id = notes.get("run_id")
    quote_id = notes.get("quote_id")
    if not run_id or not quote_id:
        raise ValueError("Razorpay payment notes must include run_id and quote_id")
    created_at = entity.get("created_at")
    paid_at = (
        datetime.fromtimestamp(created_at, UTC)
        if isinstance(created_at, int)
        else datetime.now(UTC)
    )
    return CapturedPaymentEvent(
        provider_event_id=event["id"],
        provider_payment_id=entity["id"],
        provider_order_id=entity.get("order_id"),
        amount_paise=entity["amount"],
        currency=entity["currency"],
        run_id=run_id,
        quote_id=quote_id,
        paid_at=paid_at,
        provider_link_id=entity.get("payment_link_id"),
        event_type=event_type,
    )


def _safe_metadata(parsed: CapturedPaymentEvent) -> dict[str, Any]:
    return {
        "run_id": parsed.run_id,
        "quote_id": parsed.quote_id,
        "provider_payment_id": parsed.provider_payment_id,
        "provider_order_id": parsed.provider_order_id,
        "provider_link_id": parsed.provider_link_id,
        "amount_paise": parsed.amount_paise,
        "currency": parsed.currency,
    }


def _find_payment(session: Session, parsed: CapturedPaymentEvent) -> Payment | None:
    query = select(Payment).where(Payment.run_id == parsed.run_id)
    try:
        quote_uuid = UUID(parsed.quote_id)
    except ValueError:
        quote_uuid = None
    if quote_uuid is not None:
        query = query.where(Payment.quote_id == quote_uuid)
    elif parsed.provider_link_id:
        query = query.where(Payment.provider_link_id == parsed.provider_link_id)
    else:
        return None
    return session.scalars(query).first()


def _line_items(session: Session, payment: Payment) -> list[dict[str, Any]]:
    items = session.scalars(
        select(QuoteItem)
        .where(QuoteItem.business_id == payment.business_id, QuoteItem.quote_id == payment.quote_id)
        .order_by(QuoteItem.line_no)
    ).all()
    return [
        {
            "name": item.name_snapshot,
            "quantity": str(item.quantity),
            "unit": item.sellable_unit_snapshot,
            "unit_price_paise": item.unit_price_paise,
            "tax_paise": item.tax_paise,
            "line_total_paise": item.line_total_paise,
        }
        for item in items
    ]


def _artifact_url(base_url: str, artifact_key: str) -> str:
    if not base_url:
        return artifact_key
    return f"{base_url.rstrip('/')}/{artifact_key}"


def _create_or_get_invoice(
    *,
    session: Session,
    payment: Payment,
    artifact_root: Path,
) -> Invoice:
    existing = session.scalars(
        select(Invoice).where(
            Invoice.business_id == payment.business_id,
            Invoice.payment_id == payment.id,
        )
    ).first()
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    sequence = session.get(InvoiceSequence, (payment.business_id, now.year))
    if sequence is None:
        sequence = InvoiceSequence(business_id=payment.business_id, calendar_year=now.year)
        session.add(sequence)
        session.flush()
    invoice_number = next_invoice_number(now, sequence.next_value)
    sequence.next_value += 1

    quote = session.scalars(
        select(Quote).where(
            Quote.business_id == payment.business_id,
            Quote.id == payment.quote_id,
            Quote.quote_version == payment.quote_version,
        )
    ).one()
    buyer = session.get(Buyer, quote.buyer_id)
    buyer_name = (
        (quote.buyer_snapshot or {}).get("display_name")
        or (buyer.display_name if buyer else None)
        or "Buyer"
    )
    draft = InvoiceDraft(
        invoice_number=invoice_number,
        run_id=payment.run_id,
        buyer_name=buyer_name,
        total_paise=payment.amount_paise,
        currency=payment.currency,
        issued_at=now,
        line_items=_line_items(session, payment),
        payment_reference=payment.provider_payment_id or payment.provider_reference_id,
    )
    artifact = generate_invoice_pdf_artifact(draft, artifact_root)
    invoice = Invoice(
        id=uuid4(),
        business_id=payment.business_id,
        run_id=payment.run_id,
        quote_id=payment.quote_id,
        quote_version=payment.quote_version,
        payment_id=payment.id,
        invoice_number=invoice_number,
        status="GENERATED",
        currency=payment.currency,
        total_paise=payment.amount_paise,
        snapshot={
            "buyer": quote.buyer_snapshot,
            "quote": {
                "id": str(quote.id),
                "version": quote.quote_version,
                "subtotal_paise": quote.subtotal_paise,
                "tax_paise": quote.tax_paise,
                "total_paise": quote.total_paise,
            },
            "payment": {
                "id": str(payment.id),
                "provider_payment_id": payment.provider_payment_id,
            },
            "line_items": draft.line_items,
        },
        artifact_key=artifact.artifact_key,
        artifact_sha256=artifact.artifact_sha256,
        generated_at=now,
    )
    session.add(invoice)
    session.flush()
    return invoice


def _queue_invoice_delivery(
    *,
    session: Session,
    event: PaymentEvent,
    payment: Payment,
    invoice: Invoice,
    public_artifact_base_url: str,
    admin_wa_ids: set[str],
) -> None:
    quote = session.scalars(
        select(Quote).where(
            Quote.business_id == payment.business_id,
            Quote.id == payment.quote_id,
        )
    ).one()
    buyer = session.get(Buyer, quote.buyer_id)
    recipients = []
    if buyer and buyer.whatsapp_e164:
        recipients.append(
            {
                "role": "buyer",
                "to": buyer.whatsapp_e164,
                "caption": f"Payment received. Invoice {invoice.invoice_number} is attached.",
            }
        )
    recipients.extend(
        {
            "role": "admin",
            "to": number,
            "caption": f"Payment received for {payment.run_id}. Invoice {invoice.invoice_number}.",
        }
        for number in sorted(admin_wa_ids)
    )
    for recipient in recipients:
        session.add(
            PaymentOutbox(
                id=uuid4(),
                business_id=payment.business_id,
                payment_event_id=event.id,
                topic=f"whatsapp.invoice.{recipient['role']}.{recipient['to']}",
                payload={
                    "message_type": "document",
                    "to": recipient["to"],
                    "link": _artifact_url(public_artifact_base_url, invoice.artifact_key or ""),
                    "filename": f"{invoice.invoice_number}.pdf",
                    "caption": recipient["caption"],
                    "invoice_id": str(invoice.id),
                    "payment_id": str(payment.id),
                },
            )
        )


def process_captured_payment_webhook(
    *,
    session: Session,
    payload: dict[str, Any],
    raw_body: bytes,
    artifact_root: Path,
    public_artifact_base_url: str = "",
    admin_wa_ids: set[str] | None = None,
) -> WebhookProcessingResult:
    parsed = parse_captured_payment_event(payload)
    existing_event = session.scalars(
        select(PaymentEvent).where(
            PaymentEvent.provider == "razorpay",
            PaymentEvent.provider_event_id == parsed.provider_event_id,
        )
    ).first()
    if existing_event is not None:
        invoice = session.scalars(
            select(Invoice).where(
                Invoice.business_id == existing_event.business_id,
                Invoice.payment_id == existing_event.payment_id,
            )
        ).first()
        payment = session.get(Payment, existing_event.payment_id)
        return WebhookProcessingResult(
            provider_event_id=parsed.provider_event_id,
            provider_payment_id=parsed.provider_payment_id,
            run_id=payment.run_id if payment else parsed.run_id,
            quote_id=str(payment.quote_id) if payment else parsed.quote_id,
            payment_id=str(existing_event.payment_id),
            payment_status=payment.status if payment else None,
            invoice_id=str(invoice.id) if invoice else None,
            invoice_number=invoice.invoice_number if invoice else None,
            invoice_artifact_key=invoice.artifact_key if invoice else None,
            idempotent=True,
        )

    payment = _find_payment(session, parsed)
    if payment is None:
        return WebhookProcessingResult(
            provider_event_id=parsed.provider_event_id,
            provider_payment_id=parsed.provider_payment_id,
            run_id=parsed.run_id,
            quote_id=parsed.quote_id,
            quarantined=True,
            reason="payment_not_found",
        )
    event = PaymentEvent(
        id=uuid4(),
        business_id=payment.business_id,
        payment_id=payment.id,
        provider="razorpay",
        provider_account_key=payment.provider_account_key,
        provider_event_id=parsed.provider_event_id,
        event_type=parsed.event_type,
        payload_sha256=sha256(raw_body).hexdigest(),
        safe_metadata=_safe_metadata(parsed),
        verified_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()

    if payment.amount_paise != parsed.amount_paise or payment.currency != parsed.currency:
        return WebhookProcessingResult(
            provider_event_id=parsed.provider_event_id,
            provider_payment_id=parsed.provider_payment_id,
            run_id=payment.run_id,
            quote_id=str(payment.quote_id),
            payment_id=str(payment.id),
            payment_status=payment.status,
            quarantined=True,
            reason="amount_or_currency_mismatch",
        )

    payment.provider_payment_id = parsed.provider_payment_id
    payment.provider_order_id = parsed.provider_order_id
    payment.status = "PAID"
    payment.paid_at = payment.paid_at or parsed.paid_at
    payment.updated_at = datetime.now(UTC)
    invoice = _create_or_get_invoice(session=session, payment=payment, artifact_root=artifact_root)
    _queue_invoice_delivery(
        session=session,
        event=event,
        payment=payment,
        invoice=invoice,
        public_artifact_base_url=public_artifact_base_url,
        admin_wa_ids=admin_wa_ids or set(),
    )
    return WebhookProcessingResult(
        provider_event_id=parsed.provider_event_id,
        provider_payment_id=parsed.provider_payment_id,
        run_id=payment.run_id,
        quote_id=str(payment.quote_id),
        payment_id=str(payment.id),
        payment_status=payment.status,
        invoice_id=str(invoice.id),
        invoice_number=invoice.invoice_number,
        invoice_artifact_key=invoice.artifact_key,
    )
