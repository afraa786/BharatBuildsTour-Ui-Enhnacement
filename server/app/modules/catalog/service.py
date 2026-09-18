from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.catalog import repository
from app.modules.catalog.models import Product
from app.modules.catalog.normalization import normalize_catalog_text
from app.modules.catalog.schemas import (
    CatalogCandidate,
    CatalogMatchIn,
    CatalogMatchOut,
    CatalogMatchStatus,
    MatchType,
    ProductOut,
    normalized_unit,
)


def get_products(
    session: Session,
    business_id: UUID,
    *,
    include_inactive: bool,
    limit: int,
    offset: int,
) -> list[ProductOut]:
    products = repository.list_products(
        session,
        business_id,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    return [
        ProductOut(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            sellable_unit=product.sellable_unit,
            stock_unit=product.stock_unit,
            pack_size=product.pack_size,
            indivisible=product.indivisible,
            base_unit_price_paise=product.base_unit_price_paise,
            gst_rate_bps=product.gst_rate_bps,
            active=product.active,
        )
        for product in products
    ]


def match_product(session: Session, business_id: UUID, request: CatalogMatchIn) -> CatalogMatchOut:
    normalized_query = normalize_catalog_text(request.requested_text)
    if not normalized_query:
        return _result(request, CatalogMatchStatus.NOT_FOUND, "NO_MATCH", "No match found.", [])

    matches = repository.exact_match_candidates(session, business_id, normalized_query)
    candidates = [_candidate(product, match_type) for product, match_type in matches]
    if not matches:
        return _result(request, CatalogMatchStatus.NOT_FOUND, "NO_MATCH", "No match found.", [])
    if len(matches) > 1:
        return _result(
            request,
            CatalogMatchStatus.AMBIGUOUS,
            "MULTIPLE_MATCHES",
            "Multiple active products match this request.",
            candidates,
        )

    product, match_type = matches[0]
    if normalized_unit(request.requested_unit) != normalized_unit(product.sellable_unit):
        return _result(
            request,
            CatalogMatchStatus.AMBIGUOUS,
            "UNIT_MISMATCH",
            (
                f"Unit '{request.requested_unit}' does not match product sellable unit "
                f"'{product.sellable_unit}' and no conversion exists."
            ),
            candidates,
        )

    reason_by_type = {
        MatchType.SKU: ("EXACT_SKU_MATCH", "Exact SKU match."),
        MatchType.NAME: ("EXACT_NAME_MATCH", "Exact name match."),
        MatchType.ALIAS: ("EXACT_ALIAS_MATCH", "Exact alias match."),
    }
    reason_code, reason = reason_by_type[match_type]
    return CatalogMatchOut(
        status=CatalogMatchStatus.MATCHED,
        requested_text=request.requested_text,
        selected_product_id=product.id,
        selected_sku=product.sku,
        reason=reason,
        reason_code=reason_code,
        candidates=candidates,
    )


def _candidate(product: Product, match_type: MatchType) -> CatalogCandidate:
    return CatalogCandidate(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        sellable_unit=product.sellable_unit,
        stock_unit=product.stock_unit,
        pack_size=product.pack_size,
        match_type=match_type,
    )


def _result(
    request: CatalogMatchIn,
    status: CatalogMatchStatus,
    reason_code: str,
    reason: str,
    candidates: list[CatalogCandidate],
) -> CatalogMatchOut:
    return CatalogMatchOut(
        status=status,
        requested_text=request.requested_text,
        selected_product_id=None,
        selected_sku=None,
        reason=reason,
        reason_code=reason_code,
        candidates=candidates,
    )
