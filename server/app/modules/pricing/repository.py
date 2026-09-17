from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.catalog.models import Product
from app.modules.identity.models import Business, Buyer
from app.modules.payments.models import IdempotencyKey, Payment
from app.modules.pricing.models import PricingRule, Quote, QuoteItem, QuoteLineage


def get_business(session: Session, business_id: UUID) -> Business | None:
    return session.scalar(select(Business).where(Business.id == business_id))


def get_buyer(session: Session, business_id: UUID, buyer_id: UUID) -> Buyer | None:
    return session.scalar(
        select(Buyer).where(Buyer.business_id == business_id, Buyer.id == buyer_id)
    )


def get_active_rule(session: Session, business_id: UUID, now: datetime) -> list[PricingRule]:
    return list(
        session.scalars(
            select(PricingRule).where(
                PricingRule.business_id == business_id,
                PricingRule.active.is_(True),
                PricingRule.effective_from <= now,
                (PricingRule.effective_to.is_(None)) | (PricingRule.effective_to > now),
            )
        ).all()
    )


def get_active_products(
    session: Session, business_id: UUID, product_ids: set[UUID]
) -> dict[UUID, Product]:
    return {
        product.id: product
        for product in session.scalars(
            select(Product).where(
                Product.business_id == business_id,
                Product.id.in_(product_ids),
                Product.active.is_(True),
            )
        ).all()
    }


def claim_idempotency(
    session: Session, business_id: UUID, action: str, key: str, fingerprint: str
) -> tuple[IdempotencyKey, bool]:
    inserted = session.execute(
        insert(IdempotencyKey)
        .values(
            business_id=business_id,
            action=action,
            key=key,
            request_sha256=fingerprint,
        )
        .on_conflict_do_nothing(index_elements=["business_id", "action", "key"])
        .returning(IdempotencyKey.id)
    ).scalar_one_or_none()
    record = session.scalar(
        select(IdempotencyKey)
        .where(
            IdempotencyKey.business_id == business_id,
            IdempotencyKey.action == action,
            IdempotencyKey.key == key,
        )
        .with_for_update()
    )
    assert record is not None
    return record, inserted is not None


def lock_lineage(session: Session, business_id: UUID, run_id: str) -> QuoteLineage:
    session.execute(
        insert(QuoteLineage)
        .values(business_id=business_id, run_id=run_id, latest_version=0)
        .on_conflict_do_nothing(index_elements=["business_id", "run_id"])
    )
    lineage = session.scalar(
        select(QuoteLineage)
        .where(QuoteLineage.business_id == business_id, QuoteLineage.run_id == run_id)
        .with_for_update()
    )
    assert lineage is not None
    return lineage


def get_current_quote_locked(session: Session, business_id: UUID, run_id: str) -> Quote | None:
    return session.scalar(
        select(Quote)
        .where(
            Quote.business_id == business_id,
            Quote.run_id == run_id,
            Quote.is_current.is_(True),
        )
        .with_for_update()
    )


def get_quote_locked(session: Session, business_id: UUID, quote_id: UUID) -> Quote | None:
    return session.scalar(
        select(Quote)
        .where(Quote.business_id == business_id, Quote.id == quote_id)
        .with_for_update()
    )


def get_quote_items(session: Session, business_id: UUID, quote_id: UUID) -> list[QuoteItem]:
    return list(
        session.scalars(
            select(QuoteItem)
            .where(QuoteItem.business_id == business_id, QuoteItem.quote_id == quote_id)
            .order_by(QuoteItem.line_no)
        ).all()
    )


def has_unsettled_payment(session: Session, business_id: UUID, quote_id: UUID) -> bool:
    return (
        session.scalar(
            select(Payment.id)
            .where(
                Payment.business_id == business_id,
                Payment.quote_id == quote_id,
                Payment.status.in_(["CREATED", "PENDING", "PAID", "FAILED"]),
            )
            .limit(1)
        )
        is not None
    )
