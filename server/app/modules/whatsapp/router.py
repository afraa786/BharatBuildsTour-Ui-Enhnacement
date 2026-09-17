from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.whatsapp.service import handle_webhook_payload

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


@router.get("")
def verify_webhook(
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token in settings.whatsapp_verify_tokens:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification failed")


@router.post("")
async def receive_webhook(
    request: Request, db: Annotated[Session, Depends(get_db)]
) -> dict[str, str]:
    payload = await request.json()
    await handle_webhook_payload(db, payload)
    return {"status": "received"}
