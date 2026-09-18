"""Real multi-connection PostgreSQL invoice serialization and sequence isolation."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.catalog.models import Product
from app.modules.identity.models import Business, Buyer
from app.modules.invoices import service
from app.modules.invoices.models import Invoice, InvoiceSequence
from app.modules.invoices.schemas import InvoiceGenerateIn
from app.modules.invoices.storage import LocalArtifactStore
from app.modules.payments.models import Payment, PaymentEvent
from app.modules.pricing.evidence import (
    AcceptanceEvidence,
    ApprovalEvidence,
    apply_acceptance,
    apply_approval,
)
from app.modules.pricing.schemas import QuoteCreateIn
from app.modules.pricing.service import create_quote
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]


def _setup_paid_quote(pg_engine: Engine) -> InvoiceGenerateIn:
    buyer_id, payment_id = uuid4(), uuid4()
    run_id = f"RFQ-invoice-race-{uuid4().hex}"
    with Session(pg_engine, autoflush=False) as session, session.begin():
        business = session.get(Business, DEMO_BUSINESS_ID)
        business.legal_name = "Demo Seller"
        business.billing_address = "Demo Seller Address"
        session.add(
            Buyer(
                id=buyer_id,
                business_id=DEMO_BUSINESS_ID,
                display_name="Demo Buyer",
                whatsapp_e164="+919876543210",
                legal_name="Demo Buyer Legal",
                billing_address="Demo Buyer Address",
            )
        )
        session.flush()
        product_id = session.scalar(
            select(Product.id).where(
                Product.business_id == DEMO_BUSINESS_ID, Product.sku == "LED-9W"
            )
        )
        quote = create_quote(
            session,
            DEMO_BUSINESS_ID,
            QuoteCreateIn(
                business_id=DEMO_BUSINESS_ID,
                run_id=run_id,
                buyer_id=buyer_id,
                lines=[
                    {
                        "product_id": product_id,
                        "quantity": "1.000",
                        "unit": "piece",
                        "discount_bps": 0,
                    }
                ],
            ),
            str(uuid4()),
        )
        if quote.approval_required:
            apply_approval(
                session,
                ApprovalEvidence(
                    business_id=DEMO_BUSINESS_ID,
                    run_id=run_id,
                    quote_id=quote.quote_id,
                    quote_version=1,
                    approval_id=str(uuid4()),
                    action_id=str(uuid4()),
                    action="approve_quote",
                    actor_id="owner-test",
                    decision="approved",
                    decided_at=datetime.now(UTC),
                ),
                authorized_actor_ids={"owner-test"},
            )
        apply_acceptance(
            session,
            AcceptanceEvidence(
                business_id=DEMO_BUSINESS_ID,
                run_id=run_id,
                quote_id=quote.quote_id,
                quote_version=1,
                acceptance_id=str(uuid4()),
                buyer_whatsapp_e164="+919876543210",
                source_message_id=str(uuid4()),
                channel="whatsapp",
                accepted_at=datetime.now(UTC),
            ),
        )
        session.add(
            Payment(
                id=payment_id,
                business_id=DEMO_BUSINESS_ID,
                run_id=run_id,
                quote_id=quote.quote_id,
                quote_version=1,
                status="PAID",
                amount_paise=quote.total_paise,
                currency="INR",
                provider_account_key="acc_concurrency",  # pragma: allowlist secret
                provider_reference_id=str(payment_id),
                provider_link_id=f"plink_{uuid4().hex}",
                provider_payment_id=f"pay_{uuid4().hex}",
                payment_url="https://rzp.io/i/test",
                link_expires_at=quote.expires_at,
                paid_at=datetime.now(UTC),
            )
        )
        session.flush()
        session.add(
            PaymentEvent(
                business_id=DEMO_BUSINESS_ID,
                payment_id=payment_id,
                provider="razorpay",
                provider_account_key="acc_concurrency",  # pragma: allowlist secret
                provider_event_id=f"evt_{uuid4().hex}",
                event_type="payment_link.paid",
                payload_sha256="a" * 64,
                safe_metadata={"valid_full_payment": True},
                verified_at=datetime.now(UTC),
            )
        )
    return InvoiceGenerateIn(
        business_id=DEMO_BUSINESS_ID,
        run_id=run_id,
        quote_id=quote.quote_id,
        quote_version=1,
        payment_id=payment_id,
    )


def test_concurrent_invoice_requests_reuse_one_invoice(pg_engine: Engine, monkeypatch, tmp_path):
    request = _setup_paid_quote(pg_engine)

    @contextmanager
    def isolated_transaction():
        with Session(pg_engine, autoflush=False) as session, session.begin():
            yield session

    store = LocalArtifactStore(tmp_path / "artifacts")
    monkeypatch.setattr(service, "transaction_session", isolated_transaction)
    monkeypatch.setattr(service, "LocalArtifactStore", lambda: store)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.generate_invoice, DEMO_BUSINESS_ID, request, str(uuid4()))
        second = executor.submit(service.generate_invoice, DEMO_BUSINESS_ID, request, str(uuid4()))
        results = [first.result(), second.result()]
    assert results[0].invoice_id == results[1].invoice_id
    assert results[0].invoice_number == results[1].invoice_number
    assert all(item.status == "GENERATED" for item in results)
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Invoice)
                .where(Invoice.payment_id == request.payment_id)
            )
            == 1
        )


def test_invoice_sequence_is_business_and_local_year_scoped(pg_session: Session):
    first_business = pg_session.get(Business, DEMO_BUSINESS_ID)
    other_id = uuid4()
    pg_session.execute(
        insert(Business).values(
            id=other_id,
            display_name="Other Demo",
            currency="INR",
            timezone="UTC",
            is_demo=True,
        )
    )
    second_business = pg_session.get(Business, other_id)
    starting_value = (
        pg_session.scalar(
            select(InvoiceSequence.next_value).where(
                InvoiceSequence.business_id == DEMO_BUSINESS_ID,
                InvoiceSequence.calendar_year == 2026,
            )
        )
        or 1
    )
    first = service._allocate_number(
        pg_session, first_business, datetime(2025, 12, 31, 19, 0, tzinfo=UTC)
    )
    second = service._allocate_number(
        pg_session, first_business, datetime(2025, 12, 31, 19, 0, tzinfo=UTC)
    )
    other = service._allocate_number(
        pg_session, second_business, datetime(2025, 12, 31, 19, 0, tzinfo=UTC)
    )
    assert first == f"INV-2026-{starting_value:06d}"
    assert second == f"INV-2026-{starting_value + 1:06d}"
    assert other == "INV-2025-000001"
    pg_session.flush()
    assert (
        pg_session.scalar(
            select(InvoiceSequence.next_value).where(
                InvoiceSequence.business_id == DEMO_BUSINESS_ID,
                InvoiceSequence.calendar_year == 2026,
            )
        )
        == starting_value + 2
    )
