from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.modules.catalog.normalization import normalize_catalog_text


class CatalogMatchStatus(StrEnum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


class MatchType(StrEnum):
    SKU = "sku"
    NAME = "name"
    ALIAS = "alias"


class CatalogMatchIn(BaseModel):
    business_id: UUID
    run_id: str = Field(min_length=1, max_length=255)
    requested_text: str = Field(min_length=1, max_length=255)
    requested_unit: str = Field(min_length=1, max_length=32)

    @field_validator("run_id", "requested_text", "requested_unit")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank.")
        return value


class CatalogCandidate(BaseModel):
    product_id: UUID
    sku: str
    name: str
    sellable_unit: str
    stock_unit: str
    pack_size: Decimal
    match_type: MatchType

    @field_serializer("pack_size")
    def serialize_pack_size(self, value: Decimal) -> str:
        return f"{value:.3f}"


class CatalogMatchOut(BaseModel):
    status: CatalogMatchStatus
    requested_text: str
    selected_product_id: UUID | None
    selected_sku: str | None
    reason: str
    reason_code: str
    candidates: list[CatalogCandidate]


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    sku: str
    name: str
    sellable_unit: str
    stock_unit: str
    pack_size: Decimal
    indivisible: bool
    base_unit_price_paise: int
    gst_rate_bps: int
    active: bool

    @field_serializer("pack_size")
    def serialize_pack_size(self, value: Decimal) -> str:
        return f"{value:.3f}"


def normalized_unit(value: str) -> str:
    return normalize_catalog_text(value)
