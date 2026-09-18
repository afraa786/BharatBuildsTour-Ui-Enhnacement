"""Multi-connection races for link idempotency and signed webhook replay."""

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Lock
from time import sleep
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.commercial import CommercialError
from app.modules.catalog.models import Product
from app.modules.identity.models import Buyer
from app.modules.payments import service as payment_service
from app.modules.payments.models import Payment, PaymentEvent, PaymentOutbox
from app.modules.payments.provider import ProviderLink
from app.modules.payments.schemas import PaymentLinkIn
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


class RacingProvider:
    def __init__(self):
        self.calls = 0
        self.guard = Lock()

    def create_link(self, *, reference_id, amount_paise, expire_by):
        with self.guard:
            self.calls += 1
        sleep(0.1)
        return ProviderLink(
            link_id=f"plink_{reference_id[:12]}",
            short_url="https://rzp.io/i/race-test",
            reference_id=reference_id,
            amount_paise=amount_paise,
            currency="INR",
            status="created",
        )


def _payable_quote(pg_engine: Engine) -> PaymentLinkIn:
    buyer_id = uuid4()
    run_id = f"RFQ-race-{uuid4().hex}"
    with Session(pg_engine, autoflush=False) as session, session.begin():
        session.add(
            Buyer(
                id=buyer_id,
                business_id=DEMO_BUSINESS_ID,
                display_name="Race Buyer",
                whatsapp_e164=f"+91{buyer_id.int % 10**10:010d}",
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
                    actor_id="race-owner",
                    decision="approved",
                    decided_at=datetime.now(UTC),
                ),
                authorized_actor_ids={"race-owner"},
            )
        apply_acceptance(
            session,
            AcceptanceEvidence(
                business_id=DEMO_BUSINESS_ID,
                run_id=run_id,
                quote_id=quote.quote_id,
                quote_version=1,
                acceptance_id=str(uuid4()),
                buyer_whatsapp_e164=f"+91{buyer_id.int % 10**10:010d}",
                source_message_id=str(uuid4()),
                channel="whatsapp",
                accepted_at=datetime.now(UTC),
            ),
        )
    return PaymentLinkIn(
        business_id=DEMO_BUSINESS_ID,
        run_id=run_id,
        quote_id=quote.quote_id,
        quote_version=1,
        amount_paise=quote.total_paise,
    )


def test_link_and_webhook_duplicate_races(pg_engine: Engine, monkeypatch):
    request = _payable_quote(pg_engine)
    config = SimpleNamespace(
        razorpay_account_id="acc_race_test",
        razorpay_key_id="rzp_test_race",
        razorpay_key_secret=SecretStr("synthetic-race-key"),
        razorpay_webhook_secret=SecretStr("synthetic-race-webhook"),
        razorpay_previous_webhook_secret=SecretStr(""),
    )

    @contextmanager
    def isolated_transaction():
        with Session(pg_engine, autoflush=False) as session, session.begin():
            yield session

    monkeypatch.setattr(payment_service, "transaction_session", isolated_transaction)
    monkeypatch.setattr(payment_service, "get_settings", lambda: config)
    provider = RacingProvider()

    def create():
        try:
            return payment_service.create_link(
                DEMO_BUSINESS_ID, request, "race-link-key", provider=provider
            )
        except CommercialError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create) for _ in range(2)]
        results = [future.result() for future in futures]
    assert provider.calls == 1
    successful = [item for item in results if not isinstance(item, CommercialError)]
    errors = [item for item in results if isinstance(item, CommercialError)]
    assert successful
    assert all(error.code == "IDEMPOTENCY_IN_PROGRESS" for error in errors)
    assert len({item.payment_id for item in successful}) == 1
    payment_id = successful[0].payment_id
    with Session(pg_engine) as session:
        payment = session.scalar(select(Payment).where(Payment.id == payment_id))
        link_id = payment.provider_link_id
    raw = json.dumps(
        {
            "account_id": "acc_race_test",
            "event": "payment_link.paid",
            "created_at": int(datetime.now(UTC).timestamp()),
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "amount": request.amount_paise,
                        "amount_paid": request.amount_paise,
                        "currency": "INR",
                        "status": "paid",
                    }
                },
                "payment": {
                    "entity": {
                        "id": f"pay_{uuid4().hex}",
                        "amount": request.amount_paise,
                        "currency": "INR",
                        "status": "captured",
                    }
                },
            },
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"synthetic-race-webhook", raw, hashlib.sha256).hexdigest()
    event_id = f"evt_{uuid4().hex}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(payment_service.process_webhook, raw, signature, event_id)
            for _ in range(2)
        ]
        event_results = [future.result() for future in futures]
    assert sorted(item.duplicate for item in event_results) == [False, True]
    with Session(pg_engine) as session:
        assert session.scalar(select(Payment.status).where(Payment.id == payment_id)) == "PAID"
        assert (
            session.scalar(
                select(func.count())
                .select_from(PaymentEvent)
                .where(
                    PaymentEvent.payment_id == payment_id,
                    PaymentEvent.provider_event_id == event_id,
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(PaymentOutbox)
                .join(PaymentEvent, PaymentOutbox.payment_event_id == PaymentEvent.id)
                .where(PaymentEvent.payment_id == payment_id)
            )
            == 1
        )
