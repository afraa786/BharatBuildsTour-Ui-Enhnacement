from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint("currency = 'INR'", name="ck_businesses_currency_inr"),
        CheckConstraint(
            "quote_validity_minutes IS NULL OR quote_validity_minutes > 0",
            name="ck_businesses_quote_validity_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(32))
    billing_address: Mapped[str | None] = mapped_column(String(1000))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Asia/Kolkata")
    quote_validity_minutes: Mapped[int | None] = mapped_column(Integer)
    approval_required_for_all: Mapped[bool | None] = mapped_column(Boolean)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Buyer(Base):
    __tablename__ = "buyers"
    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_buyers_business_id_id"),
        CheckConstraint(
            "display_name IS NOT NULL OR whatsapp_e164 IS NOT NULL",
            name="ck_buyers_identity_present",
        ),
        Index("ix_buyers_business_whatsapp", "business_id", "whatsapp_e164"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(255))
    whatsapp_e164: Mapped[str | None] = mapped_column(String(32))
    legal_name: Mapped[str | None] = mapped_column(String(255))
    billing_address: Mapped[str | None] = mapped_column(String(1000))
    gstin: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
