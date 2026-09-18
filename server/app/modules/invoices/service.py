"""Verified-payment invoice issuance with a retryable post-commit artifact."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.commercial import CommercialError
from app.db.session import transaction_session
from app.modules.identity.models import Business
from app.modules.inventory.models import Inventory
from app.modules.invoices.models import Invoice, InvoiceSequence
from app.modules.invoices.pdf import render_invoice_pdf
from app.modules.invoices.schemas import InvoiceGenerateIn, InvoiceOut, InvoiceStatus
from app.modules.invoices.storage import LocalArtifactStore, artifact_key
from app.modules.payments.models import Payment, PaymentEvent
from app.modules.pricing.models import Quote, QuoteItem
from app.modules.pricing.repository import claim_idempotency

ACTION = "invoice.generate"


def _fingerprint(request: InvoiceGenerateIn) -> str:
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{ACTION}:{canonical}".encode()).hexdigest()


def _response(invoice: Invoice) -> InvoiceOut:
    generated = invoice.status == InvoiceStatus.GENERATED
    return InvoiceOut(
        business_id=invoice.business_id,
        run_id=invoice.run_id,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        quote_id=invoice.quote_id,
        quote_version=invoice.quote_version,
        payment_id=invoice.payment_id,
        status=InvoiceStatus(invoice.status),
        currency=invoice.currency,
        total_paise=invoice.total_paise,
        issued_at=invoice.issued_at,
        artifact_sha256=invoice.artifact_sha256 if generated else None,
        download_url=f"/invoices/{invoice.id}/artifact" if generated else None,
    )


def get_invoice(session: Session, business_id: UUID, invoice_id: UUID) -> InvoiceOut:
    invoice = session.scalar(
        select(Invoice).where(Invoice.business_id == business_id, Invoice.id == invoice_id)
    )
    if invoice is None:
        raise CommercialError(404, "NOT_FOUND", "Invoice not found.")
    return _response(invoice)


def artifact_path(session: Session, business_id: UUID, invoice_id: UUID, store: LocalArtifactStore):
    invoice = session.scalar(
        select(Invoice).where(Invoice.business_id == business_id, Invoice.id == invoice_id)
    )
    if invoice is None:
        raise CommercialError(404, "NOT_FOUND", "Invoice not found.")
    if invoice.status != InvoiceStatus.GENERATED or not invoice.artifact_key:
        raise CommercialError(409, "ARTIFACT_NOT_READY", "Invoice PDF is not ready.")
    path = store.path(invoice.artifact_key)
    if not path.is_file():
        raise CommercialError(503, "ARTIFACT_UNAVAILABLE", "Invoice PDF is unavailable.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != invoice.artifact_sha256:
        raise CommercialError(503, "ARTIFACT_UNAVAILABLE", "Invoice PDF failed integrity check.")
    return path


def _verified_payment(session: Session, business_id: UUID, request: InvoiceGenerateIn):
    payment = session.scalar(
        select(Payment)
        .where(Payment.business_id == business_id, Payment.id == request.payment_id)
        .with_for_update()
    )
    if payment is None:
        raise CommercialError(404, "NOT_FOUND", "Payment not found.")
    if (
        payment.run_id != request.run_id
        or payment.quote_id != request.quote_id
        or payment.quote_version != request.quote_version
    ):
        raise CommercialError(
            409, "QUOTE_VERSION_MISMATCH", "Payment quote binding does not match."
        )
    if payment.status != "PAID" or payment.provider_payment_id is None or payment.paid_at is None:
        raise CommercialError(409, "PAYMENT_NOT_VERIFIED", "Verified payment is required.")
    if payment.reconciliation_hold:
        raise CommercialError(409, "PAYMENT_RECONCILIATION_REQUIRED", "Payment is on hold.")
    events = session.scalars(
        select(PaymentEvent).where(
            PaymentEvent.business_id == business_id,
            PaymentEvent.payment_id == payment.id,
            PaymentEvent.provider == "razorpay",
        )
    ).all()
    if not any(
        event.safe_metadata and event.safe_metadata.get("valid_full_payment") for event in events
    ):
        raise CommercialError(409, "PAYMENT_NOT_VERIFIED", "Signed payment evidence is required.")
    quote = session.scalar(
        select(Quote).where(Quote.business_id == business_id, Quote.id == request.quote_id)
    )
    if (
        quote is None
        or quote.run_id != request.run_id
        or quote.quote_version != request.quote_version
        or not quote.is_current
        or quote.status != "ACCEPTED"
    ):
        raise CommercialError(409, "QUOTE_VERSION_MISMATCH", "Accepted quote version is required.")
    if payment.amount_paise != quote.total_paise or payment.currency != quote.currency:
        raise CommercialError(409, "PAYMENT_AMOUNT_MISMATCH", "Payment differs from frozen quote.")
    return payment, quote


def _invoice_snapshot(
    session: Session, business: Business, quote: Quote, payment: Payment, number: str, now: datetime
) -> dict:
    if not business.is_demo:
        raise CommercialError(
            409,
            "INVOICE_TAX_CONTEXT_REQUIRED",
            "Live invoice tax classification and legal approval are not configured.",
        )
    buyer = quote.buyer_snapshot
    if (
        not business.legal_name
        or not business.billing_address
        or not buyer.get("legal_name")
        or not buyer.get("billing_address")
    ):
        raise CommercialError(
            409,
            "INVOICE_DETAILS_REQUIRED",
            "Approved seller and buyer billing details are required.",
        )
    items = list(
        session.scalars(
            select(QuoteItem)
            .where(QuoteItem.business_id == quote.business_id, QuoteItem.quote_id == quote.id)
            .order_by(QuoteItem.line_no)
        ).all()
    )
    if not items:
        raise CommercialError(409, "INVOICE_DETAILS_REQUIRED", "Quote lines are missing.")
    required: dict[UUID, Decimal] = {}
    for item in items:
        required[item.product_id] = required.get(item.product_id, Decimal(0)) + (
            item.quantity * item.pack_size
        )
    for product_id, quantity in required.items():
        inventory = session.scalar(
            select(Inventory).where(
                Inventory.business_id == quote.business_id, Inventory.product_id == product_id
            )
        )
        if inventory is None or inventory.on_hand_qty < quantity:
            raise CommercialError(409, "INSUFFICIENT_STOCK", "Paid order needs stock resolution.")
    return {
        "document_type": "DEMO_NON_TAX_INVOICE",
        "invoice_number": number,
        "issued_at": now.isoformat(),
        "business_id": str(quote.business_id),
        "run_id": quote.run_id,
        "quote_id": str(quote.id),
        "quote_version": quote.quote_version,
        "payment_id": str(payment.id),
        "provider_payment_id": payment.provider_payment_id,
        "seller": {
            "legal_name": business.legal_name,
            "billing_address": business.billing_address,
            "gstin": business.gstin,
        },
        "buyer": {
            "legal_name": buyer["legal_name"],
            "billing_address": buyer["billing_address"],
            "gstin": buyer.get("gstin"),
        },
        "items": [
            {
                "line_no": item.line_no,
                "sku": item.sku_snapshot,
                "name": item.name_snapshot,
                "quantity": f"{item.quantity:.3f}",
                "unit": item.sellable_unit_snapshot,
                "unit_price_paise": item.unit_price_paise,
                "discount_bps": item.discount_bps,
                "discount_paise": item.discount_paise,
                "taxable_paise": item.taxable_paise,
                "gst_rate_bps": item.gst_rate_bps,
                "tax_paise": item.tax_paise,
                "line_total_paise": item.line_total_paise,
            }
            for item in items
        ],
        "subtotal_paise": quote.subtotal_paise,
        "tax_paise": quote.tax_paise,
        "total_paise": quote.total_paise,
        "currency": quote.currency,
        "tax_context": quote.tax_context_snapshot,
    }


def _allocate_number(session: Session, business: Business, now: datetime) -> str:
    try:
        year = now.astimezone(ZoneInfo(business.timezone)).year
    except ZoneInfoNotFoundError as exc:
        raise CommercialError(
            409, "INVOICE_CONFIGURATION_REQUIRED", "Invalid business timezone."
        ) from exc
    session.execute(
        insert(InvoiceSequence)
        .values(business_id=business.id, calendar_year=year, next_value=1)
        .on_conflict_do_nothing(index_elements=["business_id", "calendar_year"])
    )
    sequence = session.scalar(
        select(InvoiceSequence)
        .where(InvoiceSequence.business_id == business.id, InvoiceSequence.calendar_year == year)
        .with_for_update()
    )
    assert sequence is not None
    number = sequence.next_value
    if number > 999999:
        raise CommercialError(409, "INVOICE_SEQUENCE_EXHAUSTED", "Invoice number range exhausted.")
    sequence.next_value += 1
    return f"INV-{year}-{number:06d}"


def generate_invoice(
    business_id: UUID,
    request: InvoiceGenerateIn,
    idempotency_key: str,
    *,
    store: LocalArtifactStore | None = None,
) -> InvoiceOut:
    fingerprint = _fingerprint(request)
    with transaction_session() as session:
        key, claimed = claim_idempotency(session, business_id, ACTION, idempotency_key, fingerprint)
        if key.request_sha256 != fingerprint:
            raise CommercialError(409, "IDEMPOTENCY_CONFLICT", "Key was used for another request.")
        if not claimed and key.state == "PROCESSING":
            raise CommercialError(409, "IDEMPOTENCY_IN_PROGRESS", "Invoice request is processing.")
        payment, quote = _verified_payment(session, business_id, request)
        existing = session.scalar(
            select(Invoice).where(
                Invoice.business_id == business_id, Invoice.payment_id == payment.id
            )
        )
        if existing is not None:
            invoice_id = existing.id
        else:
            other_invoice = session.scalar(
                select(Invoice).where(
                    Invoice.business_id == business_id, Invoice.quote_id == quote.id
                )
            )
            if other_invoice is not None:
                raise CommercialError(
                    409,
                    "PAYMENT_RECONCILIATION_REQUIRED",
                    "This quote version already has an invoice for another payment.",
                )
            business = session.scalar(select(Business).where(Business.id == business_id))
            if business is None:
                raise CommercialError(404, "NOT_FOUND", "Business not found.")
            # Validate legal/demo data before consuming the next number.
            _invoice_snapshot(session, business, quote, payment, "PENDING", datetime.now(UTC))
            now = datetime.now(UTC)
            number = _allocate_number(session, business, now)
            snapshot = _invoice_snapshot(session, business, quote, payment, number, now)
            invoice = Invoice(
                id=uuid4(),
                business_id=business_id,
                run_id=quote.run_id,
                quote_id=quote.id,
                quote_version=quote.quote_version,
                payment_id=payment.id,
                invoice_number=number,
                status="PENDING_ARTIFACT",
                currency=quote.currency,
                total_paise=quote.total_paise,
                snapshot=snapshot,
                issued_at=now,
            )
            session.add(invoice)
            session.flush()
            invoice_id = invoice.id
        key.state = "COMPLETED"
        key.response_status = 200
        key.response_reference = {"invoice_id": str(invoice_id)}

    storage = store or LocalArtifactStore()
    with transaction_session() as session:
        invoice = session.scalar(
            select(Invoice).where(Invoice.business_id == business_id, Invoice.id == invoice_id)
        )
        assert invoice is not None
        if invoice.status == InvoiceStatus.GENERATED:
            return _response(invoice)
        snapshot = invoice.snapshot
    try:
        pdf_bytes = render_invoice_pdf(snapshot)
        key_name = artifact_key(business_id, invoice_id)
        checksum = storage.write(key_name, pdf_bytes)
    except (OSError, ValueError) as exc:
        raise CommercialError(
            503, "ARTIFACT_GENERATION_FAILED", "Invoice is pending PDF generation; retry safely."
        ) from exc
    with transaction_session() as session:
        invoice = session.scalar(
            select(Invoice)
            .where(Invoice.business_id == business_id, Invoice.id == invoice_id)
            .with_for_update()
        )
        assert invoice is not None
        if invoice.status != InvoiceStatus.GENERATED:
            invoice.artifact_key = key_name
            invoice.artifact_sha256 = checksum
            invoice.generated_at = datetime.now(UTC)
            invoice.status = "GENERATED"
        return _response(invoice)
