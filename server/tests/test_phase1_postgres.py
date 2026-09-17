"""Phase 1 schema tests. Set STOCKAWARE_RUN_PG_TESTS=1 to use isolated PostgreSQL."""

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, delete, func, insert, inspect, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import database_url, transaction_session
from app.modules.catalog.models import Product, ProductAlias, ProductSubstitute
from app.modules.identity.models import Business, Buyer
from app.modules.inventory.models import Inventory
from app.modules.invoices.models import Invoice
from app.modules.payments.models import IdempotencyKey, Payment, PaymentEvent
from app.modules.pricing.models import PricingRule, Quote, QuoteItem, QuoteLineage
from app.seed import DEMO_BUSINESS_ID, DEMO_PRODUCTS, seed_demo

SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_ROOT.parent
EXPECTED_TABLES = {
    "businesses",
    "buyers",
    "products",
    "product_aliases",
    "product_substitutes",
    "inventory",
    "stock_movements",
    "pricing_rules",
    "quote_lineages",
    "quotes",
    "quote_items",
    "payments",
    "payment_events",
    "payment_outbox",
    "invoices",
    "invoice_sequences",
    "idempotency_keys",
}


def test_model_registry() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def _postgres_env() -> dict[str, str]:
    """Prefer the ignored local .env over conftest's dummy health-test values."""
    local = dotenv_values(REPO_ROOT / ".env") if (REPO_ROOT / ".env").exists() else {}
    result = os.environ.copy()
    for key in (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    ):
        value = local.get(key) or result.get(key)
        if value is not None:
            result[key] = value
    return result


def _alembic(env: dict[str, str], *args: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SERVER_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        pytest.fail(f"Alembic {' '.join(args)} failed:\n{completed.stdout}\n{completed.stderr}")


def _seed_cli(env: dict[str, str]) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=SERVER_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        pytest.fail(f"Seed CLI failed:\n{completed.stdout}\n{completed.stderr}")


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    if os.environ.get("STOCKAWARE_RUN_PG_TESTS") != "1":
        pytest.skip("set STOCKAWARE_RUN_PG_TESTS=1 to run isolated PostgreSQL tests")

    env = _postgres_env()
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    if any(not env.get(key) for key in required):
        pytest.fail("PostgreSQL credentials must be configured for integration tests")
    settings = Settings(
        _env_file=None,
        postgres_user=env["POSTGRES_USER"],
        postgres_password=env["POSTGRES_PASSWORD"],
        postgres_db=env["POSTGRES_DB"],
        postgres_host=env.get("POSTGRES_HOST", "127.0.0.1"),
        postgres_port=int(env.get("POSTGRES_PORT", "5432")),
    )
    database_name = f"stockaware_p1_test_{uuid4().hex[:12]}"
    assert re.fullmatch(r"stockaware_p1_test_[0-9a-f]{12}", database_name)
    admin_engine = create_engine(database_url(settings), isolation_level="AUTOCOMMIT")
    created = False
    test_engine: Engine | None = None
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        created = True
        env["POSTGRES_DB"] = database_name
        _alembic(env, "upgrade", "head")
        test_engine = create_engine(database_url(settings).set(database=database_name))
        assert EXPECTED_TABLES <= set(inspect(test_engine).get_table_names())
        _alembic(env, "downgrade", "0001_baseline")
        assert set(inspect(test_engine).get_table_names()) == {"alembic_version"}
        _alembic(env, "upgrade", "head")
        _alembic(env, "check")
        _seed_cli(env)
        _seed_cli(env)
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if created:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        admin_engine.dispose()


@pytest.fixture
def pg_session(pg_engine: Engine) -> Iterator[Session]:
    """Roll each test back; the whole generated database is removed at session end."""
    with pg_engine.connect() as connection:
        outer = connection.begin()
        session = Session(bind=connection, autoflush=False)
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


def _reject(session: Session, statement: object) -> None:
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(statement)


def _quote_chain(session: Session, run_id: str) -> tuple[UUID, UUID, UUID]:
    seed_demo(session)
    now = datetime.now(UTC)
    buyer_id, quote_id, payment_id = uuid4(), uuid4(), uuid4()
    product_id = session.execute(
        select(Product.id).where(
            Product.business_id == DEMO_BUSINESS_ID,
            Product.sku == "LED-9W",
        )
    ).scalar_one()
    rule_id = session.execute(
        select(PricingRule.id).where(PricingRule.business_id == DEMO_BUSINESS_ID)
    ).scalar_one()
    session.execute(
        insert(Buyer).values(
            id=buyer_id,
            business_id=DEMO_BUSINESS_ID,
            display_name="Demo Test Buyer",
        )
    )
    session.execute(
        insert(QuoteLineage).values(
            business_id=DEMO_BUSINESS_ID,
            run_id=run_id,
            latest_version=1,
        )
    )
    session.execute(
        insert(Quote).values(
            id=quote_id,
            business_id=DEMO_BUSINESS_ID,
            run_id=run_id,
            quote_version=1,
            buyer_id=buyer_id,
            buyer_snapshot={"display_name": "Demo Test Buyer"},
            pricing_rule_id=rule_id,
            pricing_rule_version=1,
            policy_snapshot={"fixture": True},
            status="ACCEPTED",
            subtotal_paise=12000,
            tax_paise=2160,
            total_paise=14160,
            approval_required=False,
            approval_satisfied=False,
            acceptance_id=f"accept-{run_id}",
            acceptance_evidence={"channel": "test"},
            expires_at=now + timedelta(days=1),
            generated_at=now,
            accepted_at=now,
        )
    )
    session.execute(
        insert(QuoteItem).values(
            id=uuid4(),
            business_id=DEMO_BUSINESS_ID,
            quote_id=quote_id,
            line_no=1,
            product_id=product_id,
            sku_snapshot="LED-9W",
            name_snapshot="9W LED Bulb",
            sellable_unit_snapshot="piece",
            stock_unit_snapshot="piece",
            pack_size=Decimal("1"),
            quantity=Decimal("1.000"),
            cost_unit_paise=7000,
            unit_price_paise=12000,
            gross_paise=12000,
            discount_bps=0,
            discount_paise=0,
            taxable_paise=12000,
            gst_rate_bps=1800,
            tax_paise=2160,
            line_total_paise=14160,
        )
    )
    session.execute(
        insert(Payment).values(
            id=payment_id,
            business_id=DEMO_BUSINESS_ID,
            run_id=run_id,
            quote_id=quote_id,
            quote_version=1,
            status="PAID",
            amount_paise=14160,
            provider_account_key="test-merchant",  # pragma: allowlist secret
            provider_reference_id=str(payment_id),
            provider_link_id=f"plink-{payment_id.hex}",
            provider_payment_id=f"pay-{payment_id.hex}",
            link_expires_at=now + timedelta(days=1),
            paid_at=now,
        )
    )
    return product_id, quote_id, payment_id


def test_migration_created_expected_schema(pg_engine: Engine) -> None:
    inspector = inspect(pg_engine)
    assert EXPECTED_TABLES <= set(inspector.get_table_names())
    assert "fk_invoices_business_payment_quote_run" in {
        key["name"] for key in inspector.get_foreign_keys("invoices")
    }
    assert "uq_payment_events_provider_account_event" in {
        key["name"] for key in inspector.get_unique_constraints("payment_events")
    }


def test_seed_is_repeatable_and_preserves_stock(pg_session: Session) -> None:
    first = seed_demo(pg_session)
    counts = {
        model: pg_session.scalar(select(func.count()).select_from(model))
        for model in (Business, Product, ProductAlias, ProductSubstitute, Inventory, PricingRule)
    }
    assert first == DEMO_BUSINESS_ID
    assert counts[Business] == 1
    assert counts[Product] == len(DEMO_PRODUCTS)
    assert counts[ProductAlias] == sum(len(item.aliases) for item in DEMO_PRODUCTS)
    assert counts[ProductSubstitute] == 1
    assert counts[Inventory] == len(DEMO_PRODUCTS)
    assert counts[PricingRule] == 1
    product_id = pg_session.scalar(select(Product.id).where(Product.sku == "LED-9W"))
    pg_session.execute(
        update(Inventory)
        .where(Inventory.business_id == first, Inventory.product_id == product_id)
        .values(on_hand_qty=Decimal("17.125"))
    )
    assert seed_demo(pg_session) == first
    assert {
        model: pg_session.scalar(select(func.count()).select_from(model)) for model in counts
    } == counts
    stock = pg_session.scalar(
        select(Inventory.on_hand_qty).where(
            Inventory.business_id == first,
            Inventory.product_id == product_id,
        )
    )
    assert stock == Decimal("17.125")


def test_product_uniqueness_and_business_fk(pg_session: Session) -> None:
    seed_demo(pg_session)
    other_business = uuid4()
    pg_session.execute(
        insert(Business).values(id=other_business, display_name="Other Test Business")
    )
    existing = pg_session.scalars(
        select(Product).where(Product.business_id == DEMO_BUSINESS_ID, Product.sku == "LED-9W")
    ).one()
    duplicate = {
        "id": uuid4(),
        "business_id": DEMO_BUSINESS_ID,
        "sku": existing.sku,
        "normalized_sku": existing.normalized_sku,
        "name": existing.name,
        "normalized_name": existing.normalized_name,
        "sellable_unit": existing.sellable_unit,
        "stock_unit": existing.stock_unit,
        "pack_size": Decimal("1"),
        "indivisible": True,
        "cost_unit_paise": 7000,
        "base_unit_price_paise": 12000,
        "gst_rate_bps": 1800,
    }
    _reject(pg_session, insert(Product).values(duplicate))
    pg_session.execute(
        insert(Product).values({**duplicate, "id": uuid4(), "business_id": other_business})
    )
    _reject(
        pg_session,
        insert(ProductAlias).values(
            id=uuid4(),
            business_id=other_business,
            product_id=existing.id,
            alias_text="cross-business alias",
            normalized_alias="cross business alias",
        ),
    )


def test_money_quantity_and_snapshot_checks(pg_session: Session) -> None:
    product_id, quote_id, payment_id = _quote_chain(pg_session, f"RFQ-{uuid4().hex}")
    unit_cost = pg_session.scalar(select(Product.cost_unit_paise).where(Product.id == product_id))
    assert type(unit_cost) is int
    quantity = pg_session.scalar(select(QuoteItem.quantity).where(QuoteItem.quote_id == quote_id))
    assert quantity == Decimal("1.000")
    _reject(
        pg_session,
        update(Inventory)
        .where(Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == product_id)
        .values(on_hand_qty=Decimal("-0.001")),
    )
    _reject(
        pg_session,
        update(Quote).where(Quote.id == quote_id).values(total_paise=14161),
    )
    _reject(
        pg_session,
        update(Payment).where(Payment.id == payment_id).values(run_id="RFQ-WRONG-RUN"),
    )


def test_provider_invoice_and_idempotency_uniqueness(pg_session: Session) -> None:
    _, quote_id, payment_id = _quote_chain(pg_session, f"RFQ-{uuid4().hex}")
    event_id = f"evt-{uuid4().hex}"
    event = {
        "id": uuid4(),
        "business_id": DEMO_BUSINESS_ID,
        "payment_id": payment_id,
        "provider": "razorpay",
        "provider_account_key": "test-merchant",  # pragma: allowlist secret
        "provider_event_id": event_id,
        "event_type": "payment_link.paid",
        "payload_sha256": "a" * 64,
        "verified_at": datetime.now(UTC),
    }
    pg_session.execute(insert(PaymentEvent).values(event))
    _reject(pg_session, insert(PaymentEvent).values({**event, "id": uuid4()}))

    invoice_number = f"INV-{datetime.now(UTC).year}-000001"
    invoice = {
        "id": uuid4(),
        "business_id": DEMO_BUSINESS_ID,
        "run_id": pg_session.scalar(select(Payment.run_id).where(Payment.id == payment_id)),
        "quote_id": quote_id,
        "quote_version": 1,
        "payment_id": payment_id,
        "invoice_number": invoice_number,
        "total_paise": 14160,
        "snapshot": {"fixture": True},
    }
    pg_session.execute(insert(Invoice).values(invoice))
    _reject(
        pg_session,
        insert(Invoice).values(
            {**invoice, "id": uuid4(), "invoice_number": invoice_number[:-1] + "2"}
        ),
    )
    _, second_quote, second_payment = _quote_chain(pg_session, f"RFQ-{uuid4().hex}")
    _reject(
        pg_session,
        insert(Invoice).values(
            {
                **invoice,
                "id": uuid4(),
                "run_id": pg_session.scalar(
                    select(Payment.run_id).where(Payment.id == second_payment)
                ),
                "quote_id": second_quote,
                "payment_id": second_payment,
            }
        ),
    )

    key = {
        "id": uuid4(),
        "business_id": DEMO_BUSINESS_ID,
        "action": "pricing.quote",
        "key": "same-request",
        "request_sha256": "b" * 64,
    }
    pg_session.execute(insert(IdempotencyKey).values(key))
    _reject(pg_session, insert(IdempotencyKey).values({**key, "id": uuid4()}))


def test_transaction_session_commits_and_rolls_back(
    pg_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.db import session as session_module

    monkeypatch.setattr(
        session_module,
        "get_sessionmaker",
        lambda: sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False),
    )
    committed_id, rolled_back_id = uuid4(), uuid4()
    with transaction_session() as session:
        session.add(Business(id=committed_id, display_name="Committed Test Business"))
    with Session(pg_engine) as session:
        assert session.get(Business, committed_id) is not None
    with pytest.raises(RuntimeError), transaction_session() as session:
        session.add(Business(id=rolled_back_id, display_name="Rolled Back Test Business"))
        raise RuntimeError("force rollback")
    with Session(pg_engine) as session:
        assert session.get(Business, rolled_back_id) is None
    with transaction_session() as session:
        session.execute(delete(Business).where(Business.id == committed_id))
