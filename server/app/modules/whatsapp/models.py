import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        UniqueConstraint("provider_message_id"),
        Index("ix_whatsapp_messages_provider_message_id", "provider_message_id"),
        Index("ix_whatsapp_messages_wa_id", "wa_id"),
        Index("ix_whatsapp_messages_business_created", "business_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_message_id: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    wa_id: Mapped[str] = mapped_column(String)
    phone_number_id: Mapped[str | None] = mapped_column(String, nullable=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=True
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhatsAppNumberBinding(Base):
    __tablename__ = "whatsapp_number_bindings"
    __table_args__ = (
        UniqueConstraint(
            "provider", "phone_number_id", name="uq_whatsapp_number_bindings_provider_phone"
        ),
        CheckConstraint(
            "experience IN ('owner_manager', 'customer_commerce')",
            name="ck_whatsapp_number_bindings_experience",
        ),
        Index("ix_whatsapp_number_bindings_business", "business_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="meta_whatsapp"
    )
    phone_number_id: Mapped[str] = mapped_column(String(128), nullable=False)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    experience: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    waba_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppMessageStatus(Base):
    __tablename__ = "whatsapp_message_statuses"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_message_id", "status", name="uq_whatsapp_message_statuses_event"
        ),
        CheckConstraint(
            "status IN ('sent', 'delivered', 'read', 'failed')",
            name="ck_whatsapp_message_statuses_status",
        ),
        Index("ix_whatsapp_message_statuses_phone", "phone_number_id"),
        Index("ix_whatsapp_message_statuses_business", "business_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="meta_whatsapp"
    )
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    phone_number_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient_wa_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
