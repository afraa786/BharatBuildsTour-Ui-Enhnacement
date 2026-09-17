import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        UniqueConstraint("provider_message_id"),
        Index("ix_whatsapp_messages_provider_message_id", "provider_message_id"),
        Index("ix_whatsapp_messages_wa_id", "wa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_message_id: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    wa_id: Mapped[str] = mapped_column(String)
    phone_number_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
