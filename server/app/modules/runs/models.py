import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.runs.state_machine import RunStatus


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("run_id"),
        Index("ix_runs_run_id", "run_id"),
        Index("ix_runs_buyer_wa_id", "buyer_wa_id"),
        Index("ix_runs_business_status", "business_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default=RunStatus.RECEIVED.value)
    version: Mapped[int] = mapped_column(default=1)
    source: Mapped[str] = mapped_column(String, default="whatsapp")
    buyer_wa_id: Mapped[str] = mapped_column(String)
    buyer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(String, nullable=True)
    line_items: Mapped[list] = mapped_column(JSONB, default=list)
    quote_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quote_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Historic pre-owner-dashboard rows remain intentionally unscoped and hidden.
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=True
    )
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run", order_by="RunEvent.created_at"
    )
    approvals: Mapped[list["Approval"]] = relationship(back_populates="run")


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    event: Mapped[str] = mapped_column(String)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["Run"] = relationship(back_populates="events")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    action: Mapped[str] = mapped_column(String, default="approve_quote")
    bound_run_version: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="pending")
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["Run"] = relationship(back_populates="approvals")
