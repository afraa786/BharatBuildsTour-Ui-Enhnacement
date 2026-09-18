from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header
from fastapi.responses import FileResponse

from app.api.business_context import AuthorizedBusinessId, enforce_business_claim
from app.api.commercial import CommercialError, CommercialRoute
from app.db.session import transaction_session
from app.modules.invoices import service
from app.modules.invoices.schemas import InvoiceGenerateIn, InvoiceOut
from app.modules.invoices.storage import LocalArtifactStore

router = APIRouter(tags=["invoices"], route_class=CommercialRoute)


@router.post("/invoice/generate", response_model=InvoiceOut)
def generate_invoice(
    body: InvoiceGenerateIn,
    business_id: AuthorizedBusinessId,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvoiceOut:
    enforce_business_claim(body.business_id, business_id)
    if idempotency_key is None or not idempotency_key.strip() or len(idempotency_key) > 255:
        raise CommercialError(422, "VALIDATION_ERROR", "A valid Idempotency-Key is required.")
    return service.generate_invoice(business_id, body, idempotency_key)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: UUID, business_id: AuthorizedBusinessId) -> InvoiceOut:
    with transaction_session() as session:
        return service.get_invoice(session, business_id, invoice_id)


@router.get("/invoices/{invoice_id}/artifact")
def get_invoice_artifact(invoice_id: UUID, business_id: AuthorizedBusinessId) -> FileResponse:
    with transaction_session() as session:
        path = service.artifact_path(session, business_id, invoice_id, LocalArtifactStore())
    return FileResponse(path, media_type="application/pdf", filename=f"{invoice_id}.pdf")
