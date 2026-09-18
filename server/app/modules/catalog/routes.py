from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.business_context import (
    AuthorizedBusinessId,
    enforce_business_claim,
)
from app.api.commercial import CommercialRoute
from app.db.session import get_db
from app.modules.catalog import service
from app.modules.catalog.schemas import CatalogMatchIn, CatalogMatchOut, ProductOut

router = APIRouter(tags=["catalog"], route_class=CommercialRoute)
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: DbSession,
    business_id: AuthorizedBusinessId,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProductOut]:
    return service.get_products(
        db,
        business_id,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.post("/catalog/match", response_model=CatalogMatchOut)
def match_product(
    body: CatalogMatchIn, db: DbSession, business_id: AuthorizedBusinessId
) -> CatalogMatchOut:
    enforce_business_claim(body.business_id, business_id)
    return service.match_product(db, business_id, body)
