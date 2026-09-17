from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator


class QuoteStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class QuoteLineIn(BaseModel):
    product_id: UUID
    quantity: str
    unit: str = Field(min_length=1, max_length=32)
    discount_bps: int = Field(ge=0, le=10000)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: str) -> str:
        try:
            quantity = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Quantity must be a decimal string.") from exc
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("Quantity must be finite and greater than zero.")
        if quantity.as_tuple().exponent < -3 or quantity >= Decimal("1000000000000000"):
            raise ValueError("Quantity exceeds NUMERIC(18,3) precision.")
        return value


class QuoteCreateIn(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1, max_length=160)
    buyer_id: UUID
    lines: list[QuoteLineIn] = Field(min_length=1)

    @field_validator("run_id")
    @classmethod
    def reject_blank_run(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Run ID must not be blank.")
        return value


class QuoteLineOut(BaseModel):
    product_id: UUID
    sku: str
    name: str
    quantity: Decimal
    unit: str
    unit_price_paise: int
    discount_bps: int
    discount_paise: int
    taxable_paise: int
    gst_rate_bps: int
    tax_paise: int
    line_total_paise: int

    @field_serializer("quantity")
    def serialize_quantity(self, value: Decimal) -> str:
        return f"{value:.3f}"


class QuoteOut(BaseModel):
    business_id: UUID
    run_id: str
    quote_id: UUID
    quote_version: int
    status: QuoteStatus
    currency: str
    subtotal_paise: int
    tax_paise: int
    total_paise: int
    expires_at: datetime
    approval_required: bool
    approval_satisfied: bool
    approval_reasons: list[str]
    lines: list[QuoteLineOut]
