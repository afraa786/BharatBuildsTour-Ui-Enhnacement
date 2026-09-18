"""One complete Fareed-side quote-to-demo-invoice journey on PostgreSQL."""

import hashlib
import hmac
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.api.business_context import require_business_context
from app.db.session import get_db
from app.main import app
from app.modules.identity.models import Business, Buyer
from app.modules.invoices import routes as invoice_routes
from app.modules.invoices import service as invoice_service
from app.modules.invoices.models import Invoice
from app.modules.invoices.storage import LocalArtifactStore
from app.modules.payments import routes as payment_routes
from app.modules.payments import service as payment_service
from app.modules.payments.models import Payment, PaymentEvent, PaymentOutbox
from app.modules.payments.provider import ProviderLink
from app.modules.pricing.evidence import (
    AcceptanceEvidence,
    ApprovalEvidence,
    apply_acceptance,
    apply_approval,
)
from app.seed import DEMO_BUSINESS_ID, seed_demo

pytest_plugins = ["test_phase1_postgres"]


class FakeRazorpay:
    calls = 0

    def create_link(self, *, reference_id, amount_paise, expire_by):
        self.calls += 1
        assert expire_by > datetime.now(UTC)
        return ProviderLink(
            link_id=f"plink_{reference_id[:12]}",
            short_url="https://rzp.io/i/phase6-demo",
            reference_id=reference_id,
            amount_paise=amount_paise,
            currency="INR",
            status="created",
        )


@pytest.fixture
def journey(pg_session: Session, monkeypatch, tmp_path) -> Iterator[tuple[TestClient, UUID, str]]:
    seed_demo(pg_session)
    pg_session.execute(
        update(Business)
        .where(Business.id == DEMO_BUSINESS_ID)
        .values(legal_name="Demo Seller", billing_address="Demo Seller Address")
    )
    buyer_id = uuid4()
    pg_session.execute(
        insert(Buyer).values(
            id=buyer_id,
            business_id=DEMO_BUSINESS_ID,
            display_name="Demo Buyer",
            whatsapp_e164="+919876543210",
            legal_name="Demo Buyer Legal",
            billing_address="Demo Buyer Address",
        )
    )

    @contextmanager
    def nested_transaction():
        with pg_session.begin_nested():
            yield pg_session

    def db_override():
        yield pg_session

    test_config = SimpleNamespace(
        razorpay_account_id="acc_phase6_demo",
        razorpay_key_id="rzp_test_phase6",
        razorpay_key_secret=SecretStr("synthetic-test-only-key"),
        razorpay_webhook_secret=SecretStr("synthetic-test-only-webhook"),
        razorpay_previous_webhook_secret=SecretStr(""),
    )
    monkeypatch.setattr(payment_service, "get_settings", lambda: test_config)
    fake = FakeRazorpay()
    monkeypatch.setattr(payment_service, "RazorpayProvider", lambda: fake)
    monkeypatch.setattr(payment_service, "transaction_session", nested_transaction)
    monkeypatch.setattr(payment_routes, "transaction_session", nested_transaction)
    monkeypatch.setattr(invoice_service, "transaction_session", nested_transaction)
    monkeypatch.setattr(invoice_routes, "transaction_session", nested_transaction)
    store = LocalArtifactStore(tmp_path / "artifacts")
    monkeypatch.setattr(invoice_service, "LocalArtifactStore", lambda: store)
    monkeypatch.setattr(invoice_routes, "LocalArtifactStore", lambda: store)
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_business_context] = lambda: DEMO_BUSINESS_ID
    try:
        with TestClient(app) as client:
            yield client, buyer_id, f"RFQ-phase6-{uuid4().hex}"
    finally:
        app.dependency_overrides.clear()


def test_seeded_rfq_to_signed_payment_and_demo_pdf(journey, pg_session: Session):
    client, buyer_id, run_id = journey
    match = client.post(
        "/catalog/match",
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": run_id,
            "requested_text": "9 watt led",
            "requested_unit": "piece",
        },
    )
    assert match.status_code == 200
    assert match.json()["status"] == "MATCHED"
    product_id = match.json()["selected_product_id"]
    assert product_id
    ambiguous = client.post(
        "/catalog/match",
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": run_id,
            "requested_text": "32 amp mcb",
            "requested_unit": "piece",
        },
    ).json()
    assert ambiguous["status"] == "AMBIGUOUS"
    assert ambiguous["selected_product_id"] is None
    stock = client.post(
        "/inventory/check",
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": run_id,
            "product_id": product_id,
            "requested_qty": "2.000",
            "requested_unit": "piece",
        },
    )
    assert stock.status_code == 200
    assert stock.json()["status"] == "AVAILABLE"

    quote_response = client.post(
        "/pricing/quote",
        headers={"Idempotency-Key": "phase6-quote"},
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": run_id,
            "buyer_id": str(buyer_id),
            "lines": [
                {
                    "product_id": product_id,
                    "quantity": "2.000",
                    "unit": "piece",
                    "discount_bps": 0,
                }
            ],
        },
    )
    assert quote_response.status_code == 200
    quote = quote_response.json()
    assert quote["status"] == "DRAFT" and quote["approval_required"] is True
    quote_id = UUID(quote["quote_id"])
    link_body = {
        "business_id": str(DEMO_BUSINESS_ID),
        "run_id": run_id,
        "quote_id": str(quote_id),
        "quote_version": quote["quote_version"],
        "amount_paise": quote["total_paise"],
    }
    blocked = client.post(
        "/payments/create-link", headers={"Idempotency-Key": "before-approval"}, json=link_body
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "APPROVAL_REQUIRED"

    apply_approval(
        pg_session,
        ApprovalEvidence(
            business_id=DEMO_BUSINESS_ID,
            run_id=run_id,
            quote_id=quote_id,
            quote_version=1,
            approval_id="owner-approval-phase6",
            action_id="owner-action-phase6",
            action="approve_quote",
            actor_id="owner-phase6",
            decision="approved",
            decided_at=datetime.now(UTC),
        ),
        authorized_actor_ids={"owner-phase6"},
    )
    apply_acceptance(
        pg_session,
        AcceptanceEvidence(
            business_id=DEMO_BUSINESS_ID,
            run_id=run_id,
            quote_id=quote_id,
            quote_version=1,
            acceptance_id="buyer-acceptance-phase6",
            buyer_whatsapp_e164="+919876543210",
            source_message_id="wamid-phase6",
            channel="whatsapp",
            accepted_at=datetime.now(UTC),
        ),
    )
    link = client.post(
        "/payments/create-link", headers={"Idempotency-Key": "phase6-link"}, json=link_body
    )
    assert link.status_code == 200, link.text
    payment = link.json()
    assert payment["status"] == "PENDING"
    assert payment["run_id"] == run_id
    payment_id = UUID(payment["payment_id"])
    invoice_body = {**link_body, "payment_id": str(payment_id)}
    before_payment = client.post(
        "/invoice/generate", headers={"Idempotency-Key": "before-payment"}, json=invoice_body
    )
    assert before_payment.status_code == 409
    assert before_payment.json()["error"]["code"] == "PAYMENT_NOT_VERIFIED"

    raw = json.dumps(
        {
            "entity": "event",
            "account_id": "acc_phase6_demo",
            "event": "payment_link.paid",
            "created_at": int(datetime.now(UTC).timestamp()),
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": payment["provider_link_id"],
                        "amount": quote["total_paise"],
                        "amount_paid": quote["total_paise"],
                        "currency": "INR",
                        "status": "paid",
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_phase6_demo",
                        "amount": quote["total_paise"],
                        "currency": "INR",
                        "status": "captured",
                    }
                },
            },
        },
        indent=2,
    ).encode()
    signature = hmac.new(b"synthetic-test-only-webhook", raw, hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": signature, "x-razorpay-event-id": "evt_phase6_demo"}
    assert client.post("/payments/webhook", content=raw).status_code == 401
    paid = client.post("/payments/webhook", content=raw, headers=headers)
    assert paid.status_code == 200 and paid.json()["status"] == "PAID"
    assert client.post("/payments/webhook", content=raw, headers=headers).json()["duplicate"]
    assert pg_session.scalar(select(Payment.status).where(Payment.id == payment_id)) == "PAID"
    assert pg_session.scalar(select(PaymentEvent.id).where(PaymentEvent.payment_id == payment_id))
    assert pg_session.scalar(
        select(PaymentOutbox.id).where(PaymentOutbox.topic == "payment.verified")
    )

    issued = client.post(
        "/invoice/generate", headers={"Idempotency-Key": "phase6-invoice"}, json=invoice_body
    )
    assert issued.status_code == 200, issued.text
    invoice = issued.json()
    assert invoice["status"] == "GENERATED"
    assert invoice["run_id"] == run_id
    assert invoice["payment_id"] == str(payment_id)
    assert invoice["quote_id"] == str(quote_id)
    assert invoice["total_paise"] == quote["total_paise"]
    assert client.get(invoice["download_url"]).content.startswith(b"%PDF")
    assert (
        client.post(
            "/invoice/generate", headers={"Idempotency-Key": "phase6-invoice"}, json=invoice_body
        ).json()
        == invoice
    )
    assert pg_session.scalar(select(Invoice.id).where(Invoice.payment_id == payment_id)) == UUID(
        invoice["invoice_id"]
    )
