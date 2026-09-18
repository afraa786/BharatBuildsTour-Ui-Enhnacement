from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.payments.service import (
    parse_captured_payment_event,
    process_captured_payment_webhook,
    verify_razorpay_signature,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/razorpay/webhook", status_code=status.HTTP_202_ACCEPTED)
async def razorpay_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_razorpay_signature: str = Header(default=""),
) -> dict[str, Any]:
    settings = get_settings()
    webhook_secret = settings.razorpay_webhook_secret.get_secret_value()
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="razorpay webhook not configured")

    raw_body = await request.body()
    if not verify_razorpay_signature(raw_body, x_razorpay_signature, webhook_secret):
        raise HTTPException(status_code=400, detail="invalid razorpay signature")

    payload = await request.json()
    try:
        parsed = parse_captured_payment_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not hasattr(settings, "invoice_artifact_root"):
        return {
            "accepted": True,
            "provider_event_id": parsed.provider_event_id,
            "provider_payment_id": parsed.provider_payment_id,
            "run_id": parsed.run_id,
            "quote_id": parsed.quote_id,
            "next_action": "persist_payment_event_and_generate_invoice",
        }

    try:
        result = process_captured_payment_webhook(
            session=db,
            payload=payload,
            raw_body=raw_body,
            artifact_root=Path(settings.invoice_artifact_root),
            public_artifact_base_url=settings.public_artifact_base_url,
            admin_wa_ids=settings.admin_wa_ids,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="payment persistence unavailable") from exc

    return result.model_dump(exclude_none=True)
