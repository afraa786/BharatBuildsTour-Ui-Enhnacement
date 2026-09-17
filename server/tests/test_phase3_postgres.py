"""Phase 3 quote and evidence tests on disposable migrated PostgreSQL."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.api.business_context import require_business_context
from app.api.commercial import CommercialError
from app.db.session import get_db
from app.main import app
from app.modules.catalog.models import Product
from app.modules.identity.models import Business, Buyer
from app.modules.pricing.evidence import (
    AcceptanceEvidence,
    ApprovalEvidence,
    apply_acceptance,
    apply_approval,
)
from app.modules.pricing.models import PricingRule, Quote, QuoteItem, QuoteLineage
from app.seed import DEMO_BUSINESS_ID, seed_demo

pytest_plugins = ["test_phase1_postgres"]


@pytest.fixture
def quote_client(pg_session: Session) -> Iterator[tuple[TestClient, UUID, UUID]]:
    seed_demo(pg_session)
    buyer_id = uuid4()
    pg_session.execute(
        insert(Buyer).values(
            id=buyer_id,
            business_id=DEMO_BUSINESS_ID,
            display_name="Phase 3 Test Buyer",
            whatsapp_e164="+919876543210",
        )
    )
    product_id = pg_session.scalar(
        select(Product.id).where(Product.business_id == DEMO_BUSINESS_ID, Product.sku == "LED-9W")
    )

    def session_override() -> Iterator[Session]:
        yield pg_session

    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[require_business_context] = lambda: DEMO_BUSINESS_ID
    try:
        with TestClient(app) as client:
            yield client, buyer_id, product_id
    finally:
        app.dependency_overrides.clear()


def _quote(
    client: TestClient,
    buyer_id: UUID,
    product_id: UUID,
    *,
    run_id: str = "RFQ-phase3",
    key: str = "quote-key-1",
    quantity: str = "2.000",
    discount_bps: int = 0,
    business_id: UUID = DEMO_BUSINESS_ID,
):
    return client.post(
        "/pricing/quote",
        headers={"Idempotency-Key": key},
        json={
            "business_id": str(business_id),
            "run_id": run_id,
            "buyer_id": str(buyer_id),
            "lines": [
                {
                    "product_id": str(product_id),
                    "quantity": quantity,
                    "unit": "piece",
                    "discount_bps": discount_bps,
                }
            ],
        },
    )


def test_quote_arithmetic_policy_and_snapshot(quote_client, pg_session: Session):
    client, buyer_id, product_id = quote_client
    pg_session.execute(
        update(Business)
        .where(Business.id == DEMO_BUSINESS_ID)
        .values(approval_required_for_all=False)
    )
    response = _quote(client, buyer_id, product_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "GENERATED"
    assert body["quote_version"] == 1
    assert (body["subtotal_paise"], body["tax_paise"], body["total_paise"]) == (
        24000,
        4320,
        28320,
    )
    assert body["approval_required"] is False
    assert body["lines"][0]["quantity"] == "2.000"
    assert "cost_unit_paise" not in response.text
    assert "min_margin_bps" not in response.text
    quote_id = UUID(body["quote_id"])
    item = pg_session.scalar(select(QuoteItem).where(QuoteItem.quote_id == quote_id))
    quote = pg_session.scalar(select(Quote).where(Quote.id == quote_id))
    assert item.cost_unit_paise == 7000
    assert quote.policy_snapshot["rule_version"] == 1
    pg_session.execute(
        update(Product).where(Product.id == product_id).values(name="Renamed Product")
    )
    assert item.name_snapshot == "9W LED Bulb"
    assert quote.buyer_snapshot["display_name"] == "Phase 3 Test Buyer"


def test_quote_idempotency_revision_and_stale_version(quote_client, pg_session: Session):
    client, buyer_id, product_id = quote_client
    pg_session.execute(
        update(Business)
        .where(Business.id == DEMO_BUSINESS_ID)
        .values(approval_required_for_all=False)
    )
    first = _quote(client, buyer_id, product_id, run_id="RFQ-revision", key="v1")
    replay = _quote(client, buyer_id, product_id, run_id="RFQ-revision", key="v1")
    assert replay.json() == first.json()
    conflict = _quote(
        client, buyer_id, product_id, run_id="RFQ-revision", key="v1", quantity="3.000"
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    second = _quote(client, buyer_id, product_id, run_id="RFQ-revision", key="v2", quantity="3.000")
    assert second.status_code == 200
    assert second.json()["quote_version"] == 2
    assert second.json()["quote_id"] != first.json()["quote_id"]
    old = pg_session.scalar(select(Quote).where(Quote.id == UUID(first.json()["quote_id"])))
    assert old.status == "CANCELLED" and old.is_current is False
    assert (
        pg_session.scalar(
            select(QuoteLineage.latest_version).where(
                QuoteLineage.business_id == DEMO_BUSINESS_ID,
                QuoteLineage.run_id == "RFQ-revision",
            )
        )
        == 2
    )
    assert (
        len(
            list(
                pg_session.scalars(
                    select(Quote).where(
                        Quote.business_id == DEMO_BUSINESS_ID,
                        Quote.run_id == "RFQ-revision",
                        Quote.is_current.is_(True),
                    )
                )
            )
        )
        == 1
    )


def test_quote_evidence_exact_version_and_expiry(quote_client, pg_session: Session):
    client, buyer_id, product_id = quote_client
    draft = _quote(
        client, buyer_id, product_id, run_id="RFQ-evidence", key="draft", discount_bps=1500
    )
    assert draft.status_code == 200
    body = draft.json()
    assert body["status"] == "DRAFT"
    assert body["approval_required"] is True
    assert "DISCOUNT_EXCEEDS_CAP" in body["approval_reasons"]
    evidence = ApprovalEvidence(
        business_id=DEMO_BUSINESS_ID,
        run_id="RFQ-evidence",
        quote_id=UUID(body["quote_id"]),
        quote_version=1,
        approval_id="approval-1",
        action_id="action-1",
        action="approve_quote",
        actor_id="owner-1",
        decision="approved",
        decided_at=datetime.now(UTC),
    )
    with pytest.raises(CommercialError) as unauthorized:
        apply_approval(pg_session, evidence, authorized_actor_ids={"another-owner"})
    assert unauthorized.value.status_code == 403
    apply_approval(pg_session, evidence, authorized_actor_ids={"owner-1"})
    apply_approval(pg_session, evidence, authorized_actor_ids={"owner-1"})
    assert (
        pg_session.scalar(select(Quote.status).where(Quote.id == evidence.quote_id)) == "GENERATED"
    )
    acceptance = AcceptanceEvidence(
        business_id=DEMO_BUSINESS_ID,
        run_id="RFQ-evidence",
        quote_id=evidence.quote_id,
        quote_version=1,
        acceptance_id="acceptance-1",
        buyer_whatsapp_e164="+919876543210",
        source_message_id="wamid-1",
        channel="whatsapp",
        accepted_at=datetime.now(UTC),
    )
    apply_acceptance(pg_session, acceptance)
    apply_acceptance(pg_session, acceptance)
    assert (
        pg_session.scalar(select(Quote.status).where(Quote.id == evidence.quote_id)) == "ACCEPTED"
    )

    newer = _quote(client, buyer_id, product_id, run_id="RFQ-evidence", key="v2")
    assert newer.status_code == 200
    with pytest.raises(CommercialError) as stale:
        apply_approval(pg_session, evidence, authorized_actor_ids={"owner-1"})
    assert stale.value.code == "QUOTE_VERSION_MISMATCH"


def test_quote_failure_boundaries(quote_client, pg_session: Session):
    client, buyer_id, product_id = quote_client
    missing_key = client.post(
        "/pricing/quote",
        json={
            "business_id": str(DEMO_BUSINESS_ID),
            "run_id": "RFQ-no-key",
            "buyer_id": str(buyer_id),
            "lines": [
                {
                    "product_id": str(product_id),
                    "quantity": "1.000",
                    "unit": "piece",
                    "discount_bps": 0,
                }
            ],
        },
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (
        _quote(client, buyer_id, product_id, key="bad-business", business_id=uuid4()).status_code
        == 404
    )
    assert _quote(client, uuid4(), product_id, key="bad-buyer").status_code == 404
    assert _quote(client, buyer_id, uuid4(), key="bad-product").status_code == 404
    assert (
        _quote(client, buyer_id, product_id, key="invalid-zero", discount_bps=10000).status_code
        == 422
    )

    pg_session.execute(
        update(PricingRule).where(PricingRule.business_id == DEMO_BUSINESS_ID).values(active=False)
    )
    missing_rule = _quote(client, buyer_id, product_id, key="missing-rule")
    assert missing_rule.status_code == 409
    assert missing_rule.json()["error"]["code"] == "PRICING_RULE_UNAVAILABLE"
    pg_session.execute(
        update(PricingRule).where(PricingRule.business_id == DEMO_BUSINESS_ID).values(active=True)
    )
    pg_session.execute(
        update(Business).where(Business.id == DEMO_BUSINESS_ID).values(quote_validity_minutes=None)
    )
    assert _quote(client, buyer_id, product_id, key="missing-validity").status_code == 409


def test_expired_quote_rejects_late_evidence(quote_client, pg_session: Session):
    client, buyer_id, product_id = quote_client
    body = _quote(client, buyer_id, product_id, run_id="RFQ-expire", key="expire").json()
    quote_id = UUID(body["quote_id"])
    pg_session.execute(
        update(Quote)
        .where(Quote.id == quote_id)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    evidence = ApprovalEvidence(
        business_id=DEMO_BUSINESS_ID,
        run_id="RFQ-expire",
        quote_id=quote_id,
        quote_version=1,
        approval_id="expired-approval",
        action_id="expired-action",
        action="approve_quote",
        actor_id="owner-1",
        decision="approved",
        decided_at=datetime.now(UTC) - timedelta(seconds=2),
    )
    with pytest.raises(CommercialError) as expired:
        apply_approval(pg_session, evidence, authorized_actor_ids={"owner-1"})
    assert expired.value.code == "QUOTE_EXPIRED"
