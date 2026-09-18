from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.catalog.models import Product, ProductSubstitute
from app.modules.inventory.models import Inventory


def get_active_product(session: Session, business_id: UUID, product_id: UUID) -> Product | None:
    return session.scalar(
        select(Product).where(
            Product.business_id == business_id,
            Product.id == product_id,
            Product.active.is_(True),
        )
    )


def get_inventory(session: Session, business_id: UUID, product_id: UUID) -> Inventory | None:
    return session.scalar(
        select(Inventory).where(
            Inventory.business_id == business_id,
            Inventory.product_id == product_id,
        )
    )


def ranked_substitutes(
    session: Session, business_id: UUID, product_id: UUID
) -> list[tuple[ProductSubstitute, Product, Inventory]]:
    statement = (
        select(ProductSubstitute, Product, Inventory)
        .join(
            Product,
            (Product.business_id == ProductSubstitute.business_id)
            & (Product.id == ProductSubstitute.substitute_product_id),
        )
        .join(
            Inventory,
            (Inventory.business_id == Product.business_id) & (Inventory.product_id == Product.id),
        )
        .where(
            ProductSubstitute.business_id == business_id,
            ProductSubstitute.product_id == product_id,
            Product.active.is_(True),
        )
        .order_by(ProductSubstitute.rank, Product.sku, Product.id)
    )
    return list(session.execute(statement).all())
