from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.catalog.models import Product, ProductAlias
from app.modules.catalog.schemas import MatchType


def list_products(
    session: Session,
    business_id: UUID,
    *,
    include_inactive: bool,
    limit: int,
    offset: int,
) -> list[Product]:
    statement = select(Product).where(Product.business_id == business_id)
    if not include_inactive:
        statement = statement.where(Product.active.is_(True))
    statement = statement.order_by(Product.sku, Product.id).limit(limit).offset(offset)
    return list(session.scalars(statement).all())


def exact_match_candidates(
    session: Session, business_id: UUID, normalized_query: str
) -> list[tuple[Product, MatchType]]:
    direct_statement = select(Product).where(
        Product.business_id == business_id,
        Product.active.is_(True),
        (Product.normalized_sku == normalized_query)
        | (Product.normalized_name == normalized_query),
    )
    direct_products = list(session.scalars(direct_statement).all())

    alias_statement = (
        select(Product)
        .join(
            ProductAlias,
            (ProductAlias.business_id == Product.business_id)
            & (ProductAlias.product_id == Product.id),
        )
        .where(
            Product.business_id == business_id,
            ProductAlias.business_id == business_id,
            Product.active.is_(True),
            ProductAlias.normalized_alias == normalized_query,
        )
    )
    alias_products = list(session.scalars(alias_statement).all())

    sources: dict[UUID, set[MatchType]] = defaultdict(set)
    products: dict[UUID, Product] = {}
    for product in direct_products:
        products[product.id] = product
        if product.normalized_sku == normalized_query:
            sources[product.id].add(MatchType.SKU)
        if product.normalized_name == normalized_query:
            sources[product.id].add(MatchType.NAME)
    for product in alias_products:
        products[product.id] = product
        sources[product.id].add(MatchType.ALIAS)

    priority = (MatchType.SKU, MatchType.NAME, MatchType.ALIAS)
    result = [
        (product, next(match_type for match_type in priority if match_type in sources[product_id]))
        for product_id, product in products.items()
    ]
    return sorted(result, key=lambda item: (item[0].sku, str(item[0].id)))
