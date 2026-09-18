from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class InvoiceStatus(StrEnum):
    PENDING_ARTIFACT = "PENDING_ARTIFACT"
    GENERATED = "GENERATED"


class InvoiceGenerateIn(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1, max_length=160)
    quote_id: UUID
    quote_version: int = Field(gt=0)
    payment_id: UUID

    @model_validator(mode="after")
    def reject_blank_run(self) -> "InvoiceGenerateIn":
        if not self.run_id.strip():
            raise ValueError("Run ID must not be blank.")
        return self


class InvoiceOut(BaseModel):
    business_id: UUID
    run_id: str
    invoice_id: UUID
    invoice_number: str
    quote_id: UUID
    quote_version: int
    payment_id: UUID
    status: InvoiceStatus
    currency: str
    total_paise: int
    issued_at: datetime
    artifact_sha256: str | None
    download_url: str | None
