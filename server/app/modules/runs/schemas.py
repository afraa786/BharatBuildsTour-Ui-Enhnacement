from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class AgentCraftEventOut(BaseModel):
    run_id: str
    from_agent: str
    to_agent: str
    type: str
    message: str
    status: str
    timestamp: datetime


class AdminCommandIn(BaseModel):
    actor: str
    text: str


class ApprovalActionIn(BaseModel):
    actor: str


class OutboundMessageOut(BaseModel):
    to: str
    text: str = ""
    message_type: str = "text"
    media_id: str | None = None
    link: str | None = None
    caption: str | None = None
    filename: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    name: str | None = None
    address: str | None = None
    contacts: list[dict] = Field(default_factory=list)
    interactive: dict | None = None
