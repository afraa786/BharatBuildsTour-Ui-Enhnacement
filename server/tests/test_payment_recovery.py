"""Offline payment-link recovery tests using the migrated PostgreSQL schema."""

from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

import pytest
from sqlalchemy import select
from test_phase4_postgres import _event, _link, _webhook
from test_phase4_postgres import payment_context as phase4_payment_context

from app.api.commercial import CommercialError
from app.modules.payments import service
from app.modules.payments.models import IdempotencyKey, Payment
from app.modules.payments.provider import ProviderLink

pytest_plugins = ["test_phase1_postgres"]
payment_context = phase4_payment_context


class LostResponseProvider:
    def __init__(self, *, creates_link: bool = True):
        self.creates_link = creates_link
        self.link: ProviderLink | None = None
        self.creates = 0
        self.lookups = 0
        self.lookup_error = False
        self.guard = Lock()

    def create_link(self, *, reference_id: str, amount_paise: int, expire_by: datetime):
        assert expire_by > datetime.now(UTC)
        with self.guard:
            self.creates += 1
            if self.creates_link:
                self.link = ProviderLink(
                    link_id="plink_recovered_123",
                    short_url="https://rzp.io/i/recovered123",
                    reference_id=reference_id,
                    amount_paise=amount_paise,
                    currency="INR",
                    status="created",
                )
        raise CommercialError(503, "PROVIDER_OUTCOME_UNKNOWN", "Synthetic lost response.")

    def find_link(self, *, reference_id: str) -> ProviderLink | None:
        with self.guard:
            self.lookups += 1
        if self.lookup_error:
            raise CommercialError(503, "PROVIDER_OUTCOME_UNKNOWN", "Synthetic lookup timeout.")
        return self.link


def test_lost_create_response_recovers_exact_link_once(payment_context, pg_session, monkeypatch):
    client, quote_id, amount = payment_context
    fake = LostResponseProvider()
    monkeypatch.setattr(service, "RazorpayProvider", lambda: fake)
    first = _link(client, quote_id, amount)
    assert first.status_code == 503
    assert first.json()["error"]["code"] == "PROVIDER_OUTCOME_UNKNOWN"
    payment = pg_session.scalar(select(Payment).where(Payment.quote_id == quote_id))
    assert payment.status == "CREATED"
    assert payment.provider_reference_id == str(payment.id)
    assert payment.provider_link_id is None

    # A signed event before link binding cannot be attributed and cannot mark PAID.
    early = _webhook(
        client, _event(amount, link_id="plink_recovered_123"), event_id="evt_recovery_early"
    )
    assert early.status_code == 404
    assert payment.status == "CREATED"

    recovered = _link(client, quote_id, amount)
    assert recovered.status_code == 200
    assert recovered.json()["provider_link_id"] == "plink_recovered_123"
    assert recovered.json()["status"] == "PENDING"
    assert _link(client, quote_id, amount).json() == recovered.json()
    assert fake.creates == 1
    assert fake.lookups == 1
    assert (
        pg_session.scalar(
            select(IdempotencyKey.state).where(IdempotencyKey.action == service.ACTION)
        )
        == "COMPLETED"
    )

    paid = _webhook(
        client, _event(amount, link_id="plink_recovered_123"), event_id="evt_recovery_paid"
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert (
        pg_session.scalar(
            select(Payment.status).where(Payment.id == UUID(recovered.json()["payment_id"]))
        )
        == "PAID"
    )


def test_absent_or_timed_out_lookup_never_creates_another_link(payment_context, monkeypatch):
    client, quote_id, amount = payment_context
    fake = LostResponseProvider(creates_link=False)
    monkeypatch.setattr(service, "RazorpayProvider", lambda: fake)
    assert _link(client, quote_id, amount).status_code == 503
    absent = _link(client, quote_id, amount)
    assert absent.status_code == 409
    assert absent.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"
    fake.lookup_error = True
    timed_out = _link(client, quote_id, amount)
    assert timed_out.status_code == 503
    assert timed_out.json()["error"]["code"] == "PROVIDER_OUTCOME_UNKNOWN"
    assert fake.creates == 1
    assert fake.lookups == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("reference_id", "another-intent"),
        ("amount_paise", 1),
        ("currency", "USD"),
        ("status", "cancelled"),
        ("short_url", "http://insecure.invalid/link"),
    ],
)
def test_mismatched_recovery_stays_unbound(payment_context, pg_session, monkeypatch, field, value):
    client, quote_id, amount = payment_context
    fake = LostResponseProvider()
    monkeypatch.setattr(service, "RazorpayProvider", lambda: fake)
    assert _link(client, quote_id, amount).status_code == 503
    assert fake.link is not None
    fields = vars(fake.link).copy()
    fields[field] = value
    fake.link = ProviderLink(**fields)
    rejected = _link(client, quote_id, amount)
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "PAYMENT_AMOUNT_MISMATCH"
    payment = pg_session.scalar(select(Payment).where(Payment.quote_id == quote_id))
    assert payment.status == "CREATED"
    assert payment.provider_link_id is None
    assert fake.creates == 1


def test_recovered_paid_status_waits_for_verified_webhook(payment_context, pg_session, monkeypatch):
    client, quote_id, amount = payment_context
    fake = LostResponseProvider()
    monkeypatch.setattr(service, "RazorpayProvider", lambda: fake)
    assert _link(client, quote_id, amount).status_code == 503
    assert fake.link is not None
    fake.link = ProviderLink(**{**vars(fake.link), "status": "paid"})
    recovered = _link(client, quote_id, amount)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "PENDING"
    assert recovered.json()["reconciliation_hold"] is True
    payment = pg_session.scalar(select(Payment).where(Payment.quote_id == quote_id))
    assert payment.provider_payment_id is None
    assert fake.creates == 1


def test_concurrent_recovery_reuses_one_intent(pg_engine, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from types import SimpleNamespace

    from pydantic import SecretStr
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from test_phase6_concurrency import _payable_quote

    from app.modules.identity.models import Buyer
    from app.modules.pricing.models import Quote, QuoteItem, QuoteLineage

    request = _payable_quote(pg_engine)
    config = SimpleNamespace(
        razorpay_account_id="acc_recovery_race",
        razorpay_key_id="rzp_test_recovery_race",
        razorpay_key_secret=SecretStr("synthetic-race-secret"),
    )

    @contextmanager
    def isolated_transaction():
        with Session(pg_engine, autoflush=False) as session, session.begin():
            yield session

    monkeypatch.setattr(service, "transaction_session", isolated_transaction)
    monkeypatch.setattr(service, "get_settings", lambda: config)
    fake = LostResponseProvider()
    try:
        with pytest.raises(CommercialError) as initial:
            service.create_link(request.business_id, request, "race-recovery", provider=fake)
        assert initial.value.code == "PROVIDER_OUTCOME_UNKNOWN"

        def retry():
            return service.create_link(request.business_id, request, "race-recovery", provider=fake)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(retry), pool.submit(retry)]
            results = [future.result() for future in futures]
        assert fake.creates == 1
        assert results[0].payment_id == results[1].payment_id
        assert results[0].provider_link_id == results[1].provider_link_id
    finally:
        with Session(pg_engine) as session, session.begin():
            buyer_id = session.scalar(select(Quote.buyer_id).where(Quote.id == request.quote_id))
            session.execute(delete(Payment).where(Payment.quote_id == request.quote_id))
            session.execute(
                delete(IdempotencyKey).where(
                    IdempotencyKey.business_id == request.business_id,
                    IdempotencyKey.action == service.ACTION,
                    IdempotencyKey.key == "race-recovery",
                )
            )
            session.execute(delete(QuoteItem).where(QuoteItem.quote_id == request.quote_id))
            session.execute(delete(Quote).where(Quote.id == request.quote_id))
            session.execute(
                delete(QuoteLineage).where(
                    QuoteLineage.business_id == request.business_id,
                    QuoteLineage.run_id == request.run_id,
                )
            )
            if buyer_id is not None:
                session.execute(delete(Buyer).where(Buyer.id == buyer_id))
