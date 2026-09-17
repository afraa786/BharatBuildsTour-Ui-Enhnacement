"""Contract boundary matrix for payment links and raw signed webhooks."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from test_phase4_postgres import _event, _link, _webhook
from test_phase4_postgres import payment_context as phase4_payment_context

from app.api.commercial import CommercialError
from app.modules.inventory.models import Inventory
from app.modules.payments import service
from app.modules.payments.models import IdempotencyKey, Payment, PaymentEvent, PaymentOutbox
from app.modules.pricing.models import Quote
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]


payment_context = phase4_payment_context


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("draft", "QUOTE_NOT_ACCEPTED"),
        ("approval", "APPROVAL_REQUIRED"),
        ("expired", "QUOTE_EXPIRED"),
        ("stale", "QUOTE_VERSION_MISMATCH"),
        ("stock", "INSUFFICIENT_STOCK"),
    ],
)
def test_link_preconditions(payment_context, pg_session, mutation, expected):
    client, quote_id, amount = payment_context
    quote = pg_session.scalar(select(Quote).where(Quote.id == quote_id))
    if mutation == "draft":
        quote.status = "DRAFT"
        quote.acceptance_evidence = None
    elif mutation == "approval":
        quote.status = "DRAFT"
        quote.approval_required = True
        quote.approval_satisfied = False
    elif mutation == "expired":
        quote.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    elif mutation == "stale":
        quote.is_current = False
    elif mutation == "stock":
        pg_session.execute(
            update(Inventory).where(Inventory.business_id == DEMO_BUSINESS_ID).values(on_hand_qty=0)
        )
    result = _link(client, quote_id, amount)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == expected
    assert pg_session.scalar(select(Payment.id).where(Payment.quote_id == quote_id)) is None


def test_link_business_scope_key_conflict_and_unknown_provider(
    payment_context, pg_session, monkeypatch
):
    client, quote_id, amount = payment_context
    foreign = client.post(
        "/payments/create-link",
        headers={"Idempotency-Key": "foreign"},
        json={
            "business_id": str(uuid4()),
            "run_id": "RFQ-phase4",
            "quote_id": str(quote_id),
            "quote_version": 1,
        },
    )
    assert foreign.status_code == 404

    class UnknownProvider:
        def create_link(self, **kwargs):
            raise CommercialError(503, "PROVIDER_OUTCOME_UNKNOWN", "Reconcile provider reference.")

    monkeypatch.setattr(service, "RazorpayProvider", UnknownProvider)
    first = _link(client, quote_id, amount)
    assert first.status_code == 503
    assert first.json()["error"]["code"] == "PROVIDER_OUTCOME_UNKNOWN"
    assert (
        pg_session.scalar(select(Payment.status).where(Payment.quote_id == quote_id)) == "CREATED"
    )
    assert (
        pg_session.scalar(
            select(IdempotencyKey.state).where(IdempotencyKey.action == service.ACTION)
        )
        == "PROCESSING"
    )
    assert _link(client, quote_id, amount).json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"
    assert _link(client, quote_id, amount + 1).json()["error"]["code"] == ("IDEMPOTENCY_CONFLICT")
    assert _link(client, quote_id, amount, key="another-key").json()["error"]["code"] == (
        "PAYMENT_ALREADY_EXISTS"
    )


def test_signed_formatting_partial_currency_link_account_and_authorized_only(
    payment_context, pg_session
):
    client, quote_id, amount = payment_context
    assert _link(client, quote_id, amount).status_code == 200
    event = json.loads(_event(amount))
    formatted = json.dumps(event, ensure_ascii=False, indent=3).encode() + b"\n"
    assert _webhook(client, formatted, event_id="evt_format").json()["status"] == "PAID"
    assert _webhook(client, formatted, event_id="evt_format").json()["duplicate"] is True
    payment = pg_session.scalar(select(Payment).where(Payment.quote_id == quote_id))
    assert payment.status == "PAID"

    # A later signed non-paid event or mismatched paid event cannot regress PAID.
    event["event"] = "payment.authorized"
    assert (
        _webhook(client, json.dumps(event).encode(), event_id="evt_authorized").status_code == 200
    )
    assert payment.status == "PAID"
    event["event"] = "payment_link.paid"
    event["payload"]["payment_link"]["entity"]["amount_paid"] = amount - 1
    assert _webhook(client, json.dumps(event).encode(), event_id="evt_partial").status_code == 200
    assert payment.status == "PAID"
    assert pg_session.scalar(
        select(PaymentOutbox.id).where(PaymentOutbox.topic == "payment.verified")
    )
    assert pg_session.scalar(
        select(PaymentEvent.id).where(PaymentEvent.provider_event_id == "evt_partial")
    )

    event["payload"]["payment_link"]["entity"]["currency"] = "USD"
    assert _webhook(client, json.dumps(event).encode(), event_id="evt_currency").status_code == 200
    event["payload"]["payment_link"]["entity"]["id"] = "plink_foreign"
    assert _webhook(client, json.dumps(event).encode(), event_id="evt_link").status_code == 404
    event["account_id"] = "acc_foreign"
    assert _webhook(client, json.dumps(event).encode(), event_id="evt_account").status_code == 409
    assert payment.status == "PAID"


def test_signature_is_over_exact_bytes(payment_context):
    client, quote_id, amount = payment_context
    assert _link(client, quote_id, amount).status_code == 200
    raw = _event(amount)
    signature = hmac.new(b"test-only-webhook-secret", raw, hashlib.sha256).hexdigest()
    transformed = json.dumps(json.loads(raw), indent=2).encode()
    result = client.post(
        "/payments/webhook",
        content=transformed,
        headers={"X-Razorpay-Signature": signature, "x-razorpay-event-id": "evt_trap"},
    )
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"
