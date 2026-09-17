from datetime import datetime
from decimal import Decimal
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_products_business_id_id"),
        UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),
        UniqueConstraint(
            "business_id", "normalized_sku", name="uq_products_business_normalized_sku"
        ),
        CheckConstraint("pack_size > 0", name="ck_products_pack_size_positive"),
        CheckConstraint("cost_unit_paise >= 0", name="ck_products_cost_nonnegative"),
        CheckConstraint("base_unit_price_paise > 0", name="ck_products_price_positive"),
        CheckConstraint("gst_rate_bps BETWEEN 0 AND 10000", name="ck_products_gst_rate"),
        Index("ix_products_business_normalized_name", "business_id", "normalized_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sellable_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    stock_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    pack_size: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    indivisible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    cost_unit_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    base_unit_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gst_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_product_aliases_business_product",
        ),
        UniqueConstraint(
            "business_id",
            "normalized_alias",
            "product_id",
            name="uq_product_aliases_business_alias_product",
        ),
        Index("ix_product_aliases_business_product", "business_id", "product_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    product_id: Mapped[UUID] = mapped_column(nullable=False)
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)


class ProductSubstitute(Base):
    __tablename__ = "product_substitutes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_product_substitutes_business_product",
        ),
        ForeignKeyConstraint(
            ["business_id", "substitute_product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_product_substitutes_business_substitute",
        ),
        UniqueConstraint(
            "business_id",
            "product_id",
            "substitute_product_id",
            name="uq_product_substitutes_pair",
        ),
        CheckConstraint(
            "product_id <> substitute_product_id",
            name="ck_product_substitutes_not_self",
        ),
        CheckConstraint("rank > 0", name="ck_product_substitutes_rank_positive"),
        Index("ix_product_substitutes_business_product_rank", "business_id", "product_id", "rank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    product_id: Mapped[UUID] = mapped_column(nullable=False)
    substitute_product_id: Mapped[UUID] = mapped_column(nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
