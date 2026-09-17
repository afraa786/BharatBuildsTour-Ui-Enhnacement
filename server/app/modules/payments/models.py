from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "quote_id", "quote_version", "run_id"],
            ["quotes.business_id", "quotes.id", "quotes.quote_version", "quotes.run_id"],
            ondelete="RESTRICT",
            name="fk_payments_business_quote_version_run",
        ),
        UniqueConstraint("business_id", "id", name="uq_payments_business_id_id"),
        UniqueConstraint(
            "business_id",
            "id",
            "provider_account_key",
            name="uq_payments_business_id_account",
        ),
        UniqueConstraint(
            "business_id",
            "id",
            "quote_id",
            "run_id",
            name="uq_payments_business_id_quote_run",
        ),
        UniqueConstraint(
            "provider_account_key",
            "provider_reference_id",
            name="uq_payments_provider_reference",
        ),
        UniqueConstraint(
            "provider_account_key",
            "provider_link_id",
            name="uq_payments_provider_link",
        ),
        UniqueConstraint(
            "provider_account_key",
            "provider_payment_id",
            name="uq_payments_provider_payment",
        ),
        CheckConstraint("length(trim(run_id)) > 0", name="ck_payments_run_nonempty"),
        CheckConstraint("quote_version > 0", name="ck_payments_quote_version_positive"),
        CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'CANCELLED')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount_paise > 0", name="ck_payments_amount_positive"),
        CheckConstraint("currency = 'INR'", name="ck_payments_currency_inr"),
        CheckConstraint(
            "status <> 'PAID' OR (provider_payment_id IS NOT NULL AND paid_at IS NOT NULL)",
            name="ck_payments_paid_provider_id",
        ),
        CheckConstraint(
            "status <> 'PENDING' OR (provider_link_id IS NOT NULL AND payment_url IS NOT NULL)",
            name="ck_payments_pending_link",
        ),
        Index("ix_payments_business_quote_version", "business_id", "quote_id", "quote_version"),
        Index(
            "uq_payments_one_active_or_paid_per_quote",
            "business_id",
            "quote_id",
            unique=True,
            postgresql_where=text("status IN ('CREATED', 'PENDING', 'PAID')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    quote_id: Mapped[UUID] = mapped_column(nullable=False)
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="CREATED")
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    provider_account_key: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_reference_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_link_id: Mapped[str | None] = mapped_column(String(160))
    provider_payment_id: Mapped[str | None] = mapped_column(String(160))
    provider_order_id: Mapped[str | None] = mapped_column(String(160))
    payment_url: Mapped[str | None] = mapped_column(String(1000))
    link_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reconciliation_hold: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "payment_id", "provider_account_key"],
            ["payments.business_id", "payments.id", "payments.provider_account_key"],
            ondelete="RESTRICT",
            name="fk_payment_events_business_payment_account",
        ),
        UniqueConstraint("business_id", "id", name="uq_payment_events_business_id_id"),
        UniqueConstraint(
            "provider",
            "provider_account_key",
            "provider_event_id",
            name="uq_payment_events_provider_account_event",
        ),
        Index("ix_payment_events_business_payment", "business_id", "payment_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    payment_id: Mapped[UUID] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_key: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    safe_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaymentOutbox(Base):
    __tablename__ = "payment_outbox"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "payment_event_id"],
            ["payment_events.business_id", "payment_events.id"],
            ondelete="RESTRICT",
            name="fk_payment_outbox_business_event",
        ),
        UniqueConstraint(
            "business_id",
            "payment_event_id",
            "topic",
            name="uq_payment_outbox_event_topic",
        ),
        Index(
            "ix_payment_outbox_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    payment_event_id: Mapped[UUID] = mapped_column(nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("business_id", "action", "key", name="uq_idempotency_business_action_key"),
        CheckConstraint("state IN ('PROCESSING', 'COMPLETED')", name="ck_idempotency_state"),
        CheckConstraint(
            "response_status IS NULL OR response_status BETWEEN 100 AND 599",
            name="ck_idempotency_response_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PROCESSING")
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_reference: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
