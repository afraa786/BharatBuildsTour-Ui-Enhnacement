from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingRule(Base):
    __tablename__ = "pricing_rules"
    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_pricing_rules_business_id_id"),
        UniqueConstraint(
            "business_id", "id", "version", name="uq_pricing_rules_business_id_version"
        ),
        UniqueConstraint("business_id", "version", name="uq_pricing_rules_business_version"),
        CheckConstraint("version > 0", name="ck_pricing_rules_version_positive"),
        CheckConstraint(
            "max_discount_bps BETWEEN 0 AND 10000", name="ck_pricing_rules_discount_bps"
        ),
        CheckConstraint("min_margin_bps BETWEEN 0 AND 10000", name="ck_pricing_rules_margin_bps"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_pricing_rules_effective_range",
        ),
        Index(
            "uq_pricing_rules_one_active_per_business",
            "business_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    max_discount_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    min_margin_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QuoteLineage(Base):
    __tablename__ = "quote_lineages"
    __table_args__ = (
        CheckConstraint("length(trim(run_id)) > 0", name="ck_quote_lineages_run_nonempty"),
        CheckConstraint("latest_version >= 0", name="ck_quote_lineages_latest_version"),
    )

    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), primary_key=True
    )
    run_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "run_id"],
            ["quote_lineages.business_id", "quote_lineages.run_id"],
            ondelete="RESTRICT",
            name="fk_quotes_business_run_lineage",
        ),
        ForeignKeyConstraint(
            ["business_id", "buyer_id"],
            ["buyers.business_id", "buyers.id"],
            ondelete="RESTRICT",
            name="fk_quotes_business_buyer",
        ),
        ForeignKeyConstraint(
            ["business_id", "pricing_rule_id", "pricing_rule_version"],
            ["pricing_rules.business_id", "pricing_rules.id", "pricing_rules.version"],
            ondelete="RESTRICT",
            name="fk_quotes_business_pricing_rule_version",
        ),
        UniqueConstraint("business_id", "id", name="uq_quotes_business_id_id"),
        UniqueConstraint(
            "business_id", "id", "quote_version", name="uq_quotes_business_id_version"
        ),
        UniqueConstraint(
            "business_id",
            "id",
            "quote_version",
            "run_id",
            name="uq_quotes_business_id_version_run",
        ),
        UniqueConstraint(
            "business_id", "run_id", "quote_version", name="uq_quotes_business_run_version"
        ),
        UniqueConstraint("business_id", "approval_id", name="uq_quotes_business_approval"),
        UniqueConstraint("business_id", "acceptance_id", name="uq_quotes_business_acceptance"),
        CheckConstraint("length(trim(run_id)) > 0", name="ck_quotes_run_nonempty"),
        CheckConstraint("quote_version > 0", name="ck_quotes_version_positive"),
        CheckConstraint(
            "status IN ('DRAFT', 'GENERATED', 'ACCEPTED', 'EXPIRED', 'CANCELLED')",
            name="ck_quotes_status",
        ),
        CheckConstraint("currency = 'INR'", name="ck_quotes_currency_inr"),
        CheckConstraint(
            "subtotal_paise >= 0 AND tax_paise >= 0 AND total_paise > 0",
            name="ck_quotes_amounts_positive",
        ),
        CheckConstraint("total_paise = subtotal_paise + tax_paise", name="ck_quotes_total_sum"),
        CheckConstraint(
            "NOT approval_satisfied OR (approval_id IS NOT NULL AND approval_evidence IS NOT NULL)",
            name="ck_quotes_approval_evidence",
        ),
        CheckConstraint(
            "status <> 'ACCEPTED' OR "
            "(acceptance_id IS NOT NULL AND acceptance_evidence IS NOT NULL "
            "AND accepted_at IS NOT NULL)",
            name="ck_quotes_acceptance_evidence",
        ),
        CheckConstraint(
            "status NOT IN ('GENERATED', 'ACCEPTED') OR generated_at IS NOT NULL",
            name="ck_quotes_generated_timestamp",
        ),
        CheckConstraint(
            "status NOT IN ('GENERATED', 'ACCEPTED') OR "
            "NOT approval_required OR approval_satisfied",
            name="ck_quotes_required_approval_satisfied",
        ),
        Index("ix_quotes_business_status", "business_id", "status"),
        Index("ix_quotes_business_expires", "business_id", "expires_at"),
        Index(
            "uq_quotes_business_run_current",
            "business_id",
            "run_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    buyer_id: Mapped[UUID] = mapped_column(nullable=False)
    buyer_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pricing_rule_id: Mapped[UUID] = mapped_column(nullable=False)
    pricing_rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tax_context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="DRAFT")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    subtotal_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approval_satisfied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    approval_id: Mapped[str | None] = mapped_column(String(160))
    approval_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    acceptance_id: Mapped[str | None] = mapped_column(String(160))
    acceptance_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "quote_id"],
            ["quotes.business_id", "quotes.id"],
            ondelete="RESTRICT",
            name="fk_quote_items_business_quote",
        ),
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_quote_items_business_product",
        ),
        UniqueConstraint("business_id", "quote_id", "line_no", name="uq_quote_items_line"),
        CheckConstraint("line_no > 0", name="ck_quote_items_line_positive"),
        CheckConstraint("quantity > 0", name="ck_quote_items_quantity_positive"),
        CheckConstraint("pack_size > 0", name="ck_quote_items_pack_size_positive"),
        CheckConstraint(
            "cost_unit_paise >= 0 AND unit_price_paise > 0 AND gross_paise > 0",
            name="ck_quote_items_prices",
        ),
        CheckConstraint(
            "discount_bps BETWEEN 0 AND 10000 AND gst_rate_bps BETWEEN 0 AND 10000",
            name="ck_quote_items_rates",
        ),
        CheckConstraint(
            "discount_paise >= 0 AND discount_paise <= gross_paise",
            name="ck_quote_items_discount_amount",
        ),
        CheckConstraint(
            "taxable_paise = gross_paise - discount_paise AND taxable_paise > 0",
            name="ck_quote_items_taxable",
        ),
        CheckConstraint("tax_paise >= 0", name="ck_quote_items_tax_nonnegative"),
        CheckConstraint(
            "line_total_paise = taxable_paise + tax_paise",
            name="ck_quote_items_total_sum",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    quote_id: Mapped[UUID] = mapped_column(nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID] = mapped_column(nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    sellable_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    stock_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    pack_size: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    cost_unit_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gross_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    taxable_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gst_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
