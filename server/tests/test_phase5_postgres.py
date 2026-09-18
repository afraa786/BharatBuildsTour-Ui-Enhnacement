"""Invoice issuance and artifact retry on disposable migrated PostgreSQL."""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session
from test_phase4_postgres import _event, _webhook
from test_phase4_postgres import payment_context as phase4_payment_context

from app.modules.catalog.models import Product
from app.modules.identity.models import Business, Buyer
from app.modules.invoices import routes as invoice_routes
from app.modules.invoices import service as invoice_service
from app.modules.invoices.models import Invoice, InvoiceSequence
from app.modules.invoices.storage import LocalArtifactStore
from app.modules.payments.models import Payment
from app.modules.pricing.evidence import AcceptanceEvidence, apply_acceptance
from app.modules.pricing.schemas import QuoteCreateIn, QuoteLineIn
from app.modules.pricing.service import create_quote
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]
payment_context = phase4_payment_context


@pytest.fixture
def invoice_context(payment_context, pg_session: Session, monkeypatch, tmp_path) -> Iterator[dict]:
    client, _, _ = payment_context
    pg_session.execute(
        update(Business)
        .where(Business.id == DEMO_BUSINESS_ID)
        .values(legal_name="Demo Electrical Seller", billing_address="Demo Seller Address")
    )
    buyer_id = uuid4()
    pg_session.execute(
        insert(Buyer).values(
            id=buyer_id,
            business_id=DEMO_BUSINESS_ID,
            display_name="Demo Buyer",
            whatsapp_e164=f"+91{buyer_id.int % 10**10:010d}",
            legal_name="Demo Buyer Legal",
            billing_address="Demo Buyer Address",
        )
    )
    product_id = pg_session.scalar(
        select(Product.id).where(Product.business_id == DEMO_BUSINESS_ID, Product.sku == "LED-9W")
    )
    quote = create_quote(
        pg_session,
        DEMO_BUSINESS_ID,
        QuoteCreateIn(
            business_id=DEMO_BUSINESS_ID,
            run_id="RFQ-phase5",
            buyer_id=buyer_id,
            lines=[
                QuoteLineIn(product_id=product_id, quantity="1.000", unit="piece", discount_bps=0)
            ],
        ),
        "phase5-quote",
    )
    apply_acceptance(
        pg_session,
        AcceptanceEvidence(
            business_id=DEMO_BUSINESS_ID,
            run_id=quote.run_id,
            quote_id=quote.quote_id,
            quote_version=1,
            acceptance_id="phase5-acceptance",
            buyer_whatsapp_e164=f"+91{buyer_id.int % 10**10:010d}",
            source_message_id="wamid-phase5",
            channel="whatsapp",
            accepted_at=datetime.now(UTC),
        ),
    )

    @contextmanager
    def savepoint_transaction():
        with pg_session.begin_nested():
            yield pg_session

    store = LocalArtifactStore(tmp_path / "artifacts")
    monkeypatch.setattr(invoice_service, "transaction_session", savepoint_transaction)
    monkeypatch.setattr(invoice_routes, "transaction_session", savepoint_transaction)
    monkeypatch.setattr(invoice_service, "LocalArtifactStore", lambda: store)
    monkeypatch.setattr(invoice_routes, "LocalArtifactStore", lambda: store)
    link = client.post(
        "/payments/create-link",
        headers={"Idempotency-Key": "phase5-link"},
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": quote.run_id,
            "quote_id": str(quote.quote_id),
            "quote_version": 1,
            "amount_paise": quote.total_paise,
        },
    )
    assert link.status_code == 200, link.text
    yield {
        "client": client,
        "quote": quote,
        "payment_id": UUID(link.json()["payment_id"]),
        "product_id": product_id,
        "store": store,
    }


def _invoice(context: dict, *, key="invoice-1", business_id=DEMO_BUSINESS_ID):
    quote = context["quote"]
    return context["client"].post(
        "/invoice/generate",
        headers={"Idempotency-Key": key},
        json={
            "business_id": str(business_id),
            "run_id": quote.run_id,
            "quote_id": str(quote.quote_id),
            "quote_version": quote.quote_version,
            "payment_id": str(context["payment_id"]),
        },
    )


def _pay(context: dict):
    response = _webhook(
        context["client"], _event(context["quote"].total_paise), event_id="evt_phase5"
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PAID"


def test_verified_invoice_artifact_snapshot_and_replay(invoice_context, pg_session):
    context = invoice_context
    assert _invoice(context).json()["error"]["code"] == "PAYMENT_NOT_VERIFIED"
    _pay(context)
    first = _invoice(context)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "GENERATED"
    assert body["invoice_number"].startswith(f"INV-{datetime.now(UTC).year}-")
    assert body["total_paise"] == context["quote"].total_paise
    path = context["store"].path(f"{DEMO_BUSINESS_ID}/{body['invoice_id']}.pdf")
    contents = path.read_bytes()
    assert contents.startswith(b"%PDF")
    assert body["artifact_sha256"] == hashlib.sha256(contents).hexdigest()
    assert context["client"].get(body["download_url"]).content == contents

    pg_session.execute(
        update(Product)
        .where(Product.id == context["product_id"])
        .values(name="Renamed after sale", base_unit_price_paise=999999)
    )
    again = _invoice(context)
    assert again.json() == body
    assert _invoice(context, key="another-key").json() == body
    invoice = pg_session.scalar(select(Invoice).where(Invoice.id == UUID(body["invoice_id"])))
    assert invoice.snapshot["items"][0]["name"] == "9W LED Bulb"
    assert invoice.snapshot["document_type"] == "DEMO_NON_TAX_INVOICE"
    assert (
        pg_session.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.payment_id == context["payment_id"])
        )
        == 1
    )


def test_invoice_hold_amount_mismatch_and_business_scope(invoice_context, pg_session):
    context = invoice_context
    _pay(context)
    payment = pg_session.scalar(select(Payment).where(Payment.id == context["payment_id"]))
    payment.reconciliation_hold = True
    assert _invoice(context).json()["error"]["code"] == "PAYMENT_RECONCILIATION_REQUIRED"
    payment.reconciliation_hold = False
    payment.amount_paise += 1
    assert _invoice(context).json()["error"]["code"] == "PAYMENT_AMOUNT_MISMATCH"
    payment.amount_paise -= 1
    assert _invoice(context, business_id=uuid4()).status_code == 404
    assert context["client"].get(f"/invoices/{uuid4()}").status_code == 404


def test_pdf_failure_reuses_same_number_and_id(invoice_context, pg_session, monkeypatch):
    context = invoice_context
    _pay(context)
    original = invoice_service.render_invoice_pdf

    def failed_pdf(_snapshot):
        raise OSError("fake local artifact failure")

    monkeypatch.setattr(invoice_service, "render_invoice_pdf", failed_pdf)
    failed = _invoice(context)
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "ARTIFACT_GENERATION_FAILED"
    pending = pg_session.scalar(select(Invoice).where(Invoice.payment_id == context["payment_id"]))
    invoice_id, number = pending.id, pending.invoice_number
    assert pending.status == "PENDING_ARTIFACT"
    assert context["client"].get(f"/invoices/{invoice_id}").json()["download_url"] is None
    assert context["client"].get(f"/invoices/{invoice_id}/artifact").status_code == 409
    next_value = pg_session.scalar(select(InvoiceSequence.next_value))
    monkeypatch.setattr(invoice_service, "render_invoice_pdf", original)
    restored = _invoice(context)
    assert restored.status_code == 200
    assert UUID(restored.json()["invoice_id"]) == invoice_id
    assert restored.json()["invoice_number"] == number
    assert pg_session.scalar(select(InvoiceSequence.next_value)) == next_value


def test_live_invoice_blocked_without_tax_approval(invoice_context, pg_session):
    context = invoice_context
    _pay(context)
    pg_session.execute(
        update(Business).where(Business.id == DEMO_BUSINESS_ID).values(is_demo=False)
    )
    result = _invoice(context)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "INVOICE_TAX_CONTEXT_REQUIRED"
    assert (
        pg_session.scalar(select(Invoice.id).where(Invoice.payment_id == context["payment_id"]))
        is None
    )
