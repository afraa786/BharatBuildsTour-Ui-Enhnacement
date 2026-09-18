from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.payments.models import Payment, PaymentEvent
from app.modules.pricing.models import Quote, QuoteItem


def lock_quote(session: Session, business_id: UUID, quote_id: UUID) -> Quote | None:
    return session.scalar(
        select(Quote)
        .where(Quote.business_id == business_id, Quote.id == quote_id)
        .with_for_update()
    )


def quote_items(session: Session, business_id: UUID, quote_id: UUID) -> list[QuoteItem]:
    return list(
        session.scalars(
            select(QuoteItem).where(
                QuoteItem.business_id == business_id, QuoteItem.quote_id == quote_id
            )
        ).all()
    )


def active_payment(session: Session, business_id: UUID, quote_id: UUID) -> Payment | None:
    return session.scalar(
        select(Payment)
        .where(
            Payment.business_id == business_id,
            Payment.quote_id == quote_id,
        )
        .with_for_update()
    )


def lock_payment(session: Session, business_id: UUID, payment_id: UUID) -> Payment | None:
    return session.scalar(
        select(Payment)
        .where(Payment.business_id == business_id, Payment.id == payment_id)
        .with_for_update()
    )


def lock_provider_payment(session: Session, account_key: str, link_id: str) -> Payment | None:
    return session.scalar(
        select(Payment)
        .where(Payment.provider_account_key == account_key, Payment.provider_link_id == link_id)
        .with_for_update()
    )


def get_event(session: Session, account_key: str, event_id: str) -> PaymentEvent | None:
    return session.scalar(
        select(PaymentEvent).where(
            PaymentEvent.provider == "razorpay",
            PaymentEvent.provider_account_key == account_key,
            PaymentEvent.provider_event_id == event_id,
        )
    )
