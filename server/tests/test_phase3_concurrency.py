"""PostgreSQL locking and uniqueness tests for quote creation races."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.catalog.models import Product
from app.modules.identity.models import Buyer
from app.modules.pricing.models import Quote
from app.modules.pricing.schemas import QuoteCreateIn
from app.modules.pricing.service import create_quote
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]


def _setup(pg_engine: Engine):
    buyer_id = uuid4()
    with Session(pg_engine) as session, session.begin():
        session.execute(
            insert(Buyer).values(
                id=buyer_id,
                business_id=DEMO_BUSINESS_ID,
                display_name="Concurrency Test Buyer",
            )
        )
        product_id = session.scalar(
            select(Product.id).where(
                Product.business_id == DEMO_BUSINESS_ID, Product.sku == "LED-9W"
            )
        )
    return buyer_id, product_id


def _create(pg_engine: Engine, request: QuoteCreateIn, key: str):
    with Session(pg_engine, autoflush=False) as session, session.begin():
        return create_quote(session, DEMO_BUSINESS_ID, request, key)


def test_concurrent_quote_revisions_have_one_current_version(pg_engine: Engine):
    buyer_id, product_id = _setup(pg_engine)
    run_id = f"RFQ-concurrent-{uuid4().hex}"
    request = QuoteCreateIn(
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
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_create, pg_engine, request, "parallel-key-1")
        second = executor.submit(_create, pg_engine, request, "parallel-key-2")
        results = [first.result(), second.result()]
    assert {result.quote_version for result in results} == {1, 2}
    assert len({result.quote_id for result in results}) == 2
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Quote)
                .where(
                    Quote.business_id == DEMO_BUSINESS_ID,
                    Quote.run_id == run_id,
                    Quote.is_current.is_(True),
                )
            )
            == 1
        )


def test_concurrent_idempotency_replays_same_quote(pg_engine: Engine):
    buyer_id, product_id = _setup(pg_engine)
    request = QuoteCreateIn(
        business_id=DEMO_BUSINESS_ID,
        run_id=f"RFQ-idempotent-{uuid4().hex}",
        buyer_id=buyer_id,
        lines=[
            {
                "product_id": product_id,
                "quantity": "1.000",
                "unit": "piece",
                "discount_bps": 0,
            }
        ],
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_create, pg_engine, request, "same-parallel-key")
        second = executor.submit(_create, pg_engine, request, "same-parallel-key")
        results = [first.result(), second.result()]
    assert results[0].quote_id == results[1].quote_id
    assert results[0].model_dump(mode="json") == results[1].model_dump(mode="json")
