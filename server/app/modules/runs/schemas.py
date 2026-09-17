from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    status: str
    version: int
    source: str
    buyer_wa_id: str
    buyer_name: str | None
    line_items: list
    quote_snapshot: dict | None
    quote_id: str | None
    payment_id: str | None
    invoice_id: str | None
    created_at: datetime
    updated_at: datetime


class TimelineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    role: str
    event: str
    run_id: str
    metadata: dict | None = None


class AdminCommandIn(BaseModel):
    actor: str
    text: str


class ApprovalActionIn(BaseModel):
    actor: str


class OutboundMessageOut(BaseModel):
    to: str
    text: str
