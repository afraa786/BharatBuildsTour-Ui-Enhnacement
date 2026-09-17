from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_inventory_business_product",
        ),
        CheckConstraint("on_hand_qty >= 0", name="ck_inventory_on_hand_nonnegative"),
        CheckConstraint(
            "reorder_threshold IS NULL OR reorder_threshold >= 0",
            name="ck_inventory_reorder_threshold_nonnegative",
        ),
        CheckConstraint("version > 0", name="ck_inventory_version_positive"),
    )

    business_id: Mapped[UUID] = mapped_column(primary_key=True)
    product_id: Mapped[UUID] = mapped_column(primary_key=True)
    on_hand_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reorder_threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["inventory.business_id", "inventory.product_id"],
            ondelete="RESTRICT",
            name="fk_stock_movements_business_inventory",
        ),
        UniqueConstraint("business_id", "movement_key", name="uq_stock_movements_business_key"),
        CheckConstraint("quantity_delta <> 0", name="ck_stock_movements_delta_nonzero"),
        CheckConstraint("resulting_on_hand_qty >= 0", name="ck_stock_movements_result_nonnegative"),
        Index(
            "ix_stock_movements_business_product_created", "business_id", "product_id", "created_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(nullable=False)
    product_id: Mapped[UUID] = mapped_column(nullable=False)
    movement_key: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    resulting_on_hand_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
