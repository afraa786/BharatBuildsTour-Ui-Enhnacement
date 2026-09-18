from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PaymentLinkIn(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1, max_length=160)
    quote_id: UUID
    quote_version: int = Field(gt=0)
    amount_paise: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def reject_blank_run(self) -> "PaymentLinkIn":
        if not self.run_id.strip():
            raise ValueError("Run ID must not be blank.")
        return self


class PaymentOut(BaseModel):
    business_id: UUID
    run_id: str
    payment_id: UUID
    quote_id: UUID
    quote_version: int
    status: PaymentStatus
    amount_paise: int
    currency: str
    provider_link_id: str | None
    payment_url: str | None
    link_expires_at: datetime
    reconciliation_hold: bool


class WebhookOut(BaseModel):
    received: bool = True
    duplicate: bool = False
    payment_id: UUID | None = None
    status: PaymentStatus | None = None
    reconciliation_hold: bool = False
