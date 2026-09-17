from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.business_context import AuthorizedBusinessId, enforce_business_claim
from app.api.commercial import CommercialRoute
from app.db.session import get_db
from app.modules.inventory import service
from app.modules.inventory.schemas import InventoryCheckIn, InventoryCheckOut

router = APIRouter(tags=["inventory"], route_class=CommercialRoute)
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/inventory/check", response_model=InventoryCheckOut)
def check_inventory(
    body: InventoryCheckIn, db: DbSession, business_id: AuthorizedBusinessId
) -> InventoryCheckOut:
    enforce_business_claim(body.business_id, business_id)
    return service.check_stock(db, business_id, body)
