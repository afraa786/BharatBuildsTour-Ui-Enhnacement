from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator


class StockStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    LOW_STOCK = "LOW_STOCK"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class InventoryCheckIn(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1, max_length=255)
    product_id: UUID
    requested_qty: str
    requested_unit: str | None = Field(default=None, max_length=32)

    @field_validator("run_id")
    @classmethod
    def reject_blank_run(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank.")
        return value

    @field_validator("requested_qty")
    @classmethod
    def validate_quantity(cls, value: str) -> str:
        try:
            quantity = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Requested quantity must be a decimal string.") from exc
        if not quantity.is_finite():
            raise ValueError("Requested quantity must be finite.")
        if quantity <= 0:
            raise ValueError("Requested quantity must be greater than zero.")
        if quantity.as_tuple().exponent < -3:
            raise ValueError("Requested quantity exceeds maximum 3 decimal places precision.")
        if quantity >= Decimal("1000000000000000"):
            raise ValueError("Requested quantity exceeds NUMERIC(18,3) range.")
        return value


class SubstituteOut(BaseModel):
    product_id: UUID
    sku: str
    name: str
    rank: int
    reason: str | None


class InventoryCheckOut(BaseModel):
    status: StockStatus
    product_id: UUID
    requested_qty: Decimal
    stock_unit: str
    on_hand_qty: Decimal
    available_qty: Decimal
    checked_at: datetime
    substitutes: list[SubstituteOut]

    @field_serializer("requested_qty", "on_hand_qty", "available_qty")
    def serialize_quantity(self, value: Decimal) -> str:
        return f"{value:.3f}"
