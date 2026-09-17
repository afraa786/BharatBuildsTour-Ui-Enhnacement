from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.business_context import AuthorizedBusinessId, enforce_business_claim
from app.api.commercial import CommercialError, CommercialRoute
from app.db.session import get_db
from app.modules.pricing import service
from app.modules.pricing.schemas import QuoteCreateIn, QuoteOut

router = APIRouter(tags=["pricing"], route_class=CommercialRoute)
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/pricing/quote", response_model=QuoteOut)
def create_quote(
    body: QuoteCreateIn,
    db: DbSession,
    business_id: AuthorizedBusinessId,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> QuoteOut:
    enforce_business_claim(body.business_id, business_id)
    if idempotency_key is None or not idempotency_key.strip() or len(idempotency_key) > 255:
        raise CommercialError(422, "VALIDATION_ERROR", "A valid Idempotency-Key is required.")
    return service.create_quote(db, business_id, body, idempotency_key)
