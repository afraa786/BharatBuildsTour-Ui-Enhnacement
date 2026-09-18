"""Payment protocol against migrated disposable PostgreSQL; provider is always fake."""

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
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.api.business_context import require_business_context
from app.main import app
from app.modules.catalog.models import Product
from app.modules.identity.models import Business, Buyer
from app.modules.payments import routes, service
from app.modules.payments.models import Payment, PaymentEvent, PaymentOutbox
from app.modules.payments.provider import ProviderLink
from app.modules.pricing.evidence import AcceptanceEvidence, apply_acceptance
from app.modules.pricing.schemas import QuoteCreateIn, QuoteLineIn
from app.modules.pricing.service import create_quote
from app.seed import DEMO_BUSINESS_ID, seed_demo

pytest_plugins = ["test_phase1_postgres"]


class FakeProvider:
    calls = 0

    def create_link(self, *, reference_id, amount_paise, expire_by):
        self.calls += 1
        assert expire_by > datetime.now(UTC)
        return ProviderLink(
            link_id="plink_test_123",
            short_url="https://rzp.io/i/test123",
            reference_id=reference_id,
            amount_paise=amount_paise,
            currency="INR",
            status="created",
        )


@pytest.fixture
def payment_context(pg_session: Session, monkeypatch) -> Iterator[tuple[TestClient, UUID, int]]:
    seed_demo(pg_session)
    pg_session.execute(
        update(Business)
        .where(Business.id == DEMO_BUSINESS_ID)
        .values(approval_required_for_all=False)
    )
    buyer_id = uuid4()
    pg_session.execute(
        insert(Buyer).values(
            id=buyer_id,
            business_id=DEMO_BUSINESS_ID,
            display_name="Payment Test Buyer",
            whatsapp_e164=f"+91{buyer_id.int % 10**10:010d}",
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
            run_id="RFQ-phase4",
            buyer_id=buyer_id,
            lines=[
                QuoteLineIn(
                    product_id=product_id,
                    quantity="1.000",
                    unit="piece",
                    discount_bps=0,
                )
            ],
        ),
        "phase4-quote",
    )
    apply_acceptance(
        pg_session,
        AcceptanceEvidence(
            business_id=DEMO_BUSINESS_ID,
            run_id=quote.run_id,
            quote_id=quote.quote_id,
            quote_version=quote.quote_version,
            acceptance_id="phase4-acceptance",
            buyer_whatsapp_e164=f"+91{buyer_id.int % 10**10:010d}",
            source_message_id="wamid-phase4",
            channel="whatsapp",
            accepted_at=datetime.now(UTC),
        ),
    )

    @contextmanager
    def savepoint_transaction():
        with pg_session.begin_nested():
            yield pg_session

    config = SimpleNamespace(
        razorpay_account_id="acc_test_123",
        razorpay_key_id="rzp_test_dummy",
        razorpay_key_secret=SecretStr("test-only-key-secret"),
        razorpay_webhook_secret=SecretStr("test-only-webhook-secret"),
        razorpay_previous_webhook_secret=SecretStr("previous-test-secret"),
    )
    monkeypatch.setattr(service, "transaction_session", savepoint_transaction)
    monkeypatch.setattr(routes, "transaction_session", savepoint_transaction)
    monkeypatch.setattr(service, "get_settings", lambda: config)
    fake = FakeProvider()
    monkeypatch.setattr(service, "RazorpayProvider", lambda: fake)
    app.dependency_overrides[require_business_context] = lambda: DEMO_BUSINESS_ID
    try:
        with TestClient(app) as client:
            yield client, quote.quote_id, quote.total_paise
    finally:
        app.dependency_overrides.clear()


def _link(client: TestClient, quote_id: UUID, amount: int, *, key="link-1"):
    return client.post(
        "/payments/create-link",
        headers={"Idempotency-Key": key},
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": "RFQ-phase4",
            "quote_id": str(quote_id),
            "quote_version": 1,
            "amount_paise": amount,
        },
    )


def _event(amount: int, *, link_id="plink_test_123", payment_id="pay_test_123") -> bytes:
    return json.dumps(
        {
            "entity": "event",
            "account_id": "acc_test_123",
            "event": "payment_link.paid",
            "created_at": int(datetime.now(UTC).timestamp()),
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "amount": amount,
                        "amount_paid": amount,
                        "currency": "INR",
                        "status": "paid",
                    }
                },
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "amount": amount,
                        "currency": "INR",
                        "status": "captured",
                    }
                },
            },
        },
        separators=(",", ":"),
    ).encode()


def _webhook(
    client: TestClient, raw: bytes, event_id="evt_test_123", secret=b"test-only-webhook-secret"
):
    signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    return client.post(
        "/payments/webhook",
        content=raw,
        headers={"X-Razorpay-Signature": signature, "x-razorpay-event-id": event_id},
    )


def test_link_exact_quote_idempotency_and_verified_payment(payment_context, pg_session):
    client, quote_id, amount = payment_context
    mismatched = _link(client, quote_id, amount + 1, key="bad-amount")
    assert mismatched.status_code == 409
    assert mismatched.json()["error"]["code"] == "PAYMENT_AMOUNT_MISMATCH"
    first = _link(client, quote_id, amount)
    assert first.status_code == 200
    assert first.json()["status"] == "PENDING"
    assert first.json()["amount_paise"] == amount
    assert _link(client, quote_id, amount).json() == first.json()
    assert _link(client, quote_id, amount, key="another-link").json()["error"]["code"] == (
        "PAYMENT_ALREADY_EXISTS"
    )
    payment_id = UUID(first.json()["payment_id"])
    assert client.get(f"/payments/{payment_id}").json()["status"] == "PENDING"
    raw = _event(amount)
    assert client.post("/payments/webhook", content=raw).status_code == 401
    paid = _webhook(client, raw)
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert paid.json()["reconciliation_hold"] is False
    assert _webhook(client, raw).json()["duplicate"] is True
    assert pg_session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
    assert pg_session.scalar(select(func.count()).select_from(PaymentOutbox)) == 1
    assert pg_session.scalar(select(Payment.status).where(Payment.id == payment_id)) == "PAID"


def test_webhook_mismatch_quarantine_replay_and_conflict(payment_context, pg_session):
    client, quote_id, amount = payment_context
    assert _link(client, quote_id, amount).status_code == 200
    mismatched_raw = _event(amount + 1)
    wrong = _webhook(client, mismatched_raw, event_id="evt_mismatch")
    assert wrong.status_code == 200
    assert wrong.json()["status"] == "PENDING"
    assert _webhook(client, mismatched_raw, event_id="evt_mismatch").json()["duplicate"] is True
    conflict = _webhook(client, _event(amount), event_id="evt_mismatch")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE_EVENT"
    assert pg_session.scalar(select(func.count()).select_from(PaymentOutbox)) == 1
    assert pg_session.scalar(select(PaymentOutbox.topic)) == "payment.reconciliation_required"


def test_previous_webhook_secret_and_late_paid_hold(payment_context, pg_session):
    client, quote_id, amount = payment_context
    assert _link(client, quote_id, amount).status_code == 200
    payment = pg_session.scalar(select(Payment).where(Payment.quote_id == quote_id))
    payment.status = "EXPIRED"
    paid = _webhook(client, _event(amount), event_id="evt_late", secret=b"previous-test-secret")
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert paid.json()["reconciliation_hold"] is True
