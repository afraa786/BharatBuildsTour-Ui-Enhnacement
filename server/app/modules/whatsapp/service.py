from collections.abc import Iterator
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.runs import service as runs_service
from app.modules.whatsapp import client
from app.modules.whatsapp.models import WhatsAppMessage


def _extract_inbound_messages(payload: dict) -> Iterator[dict]:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            contacts = {
                c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])
            }
            for message in value.get("messages", []):
                yield {
                    "phone_number_id": phone_number_id,
                    "wa_id": message.get("from"),
                    "buyer_name": contacts.get(message.get("from")),
                    "message_id": message.get("id"),
                    "type": message.get("type"),
                    "text": message.get("text", {}).get("body", ""),
                }


def _log_message(
    db: Session,
    provider_message_id: str,
    direction: str,
    wa_id: str,
    phone_number_id: str | None,
    payload: dict,
) -> bool:
    """Returns False if this provider_message_id was already logged (duplicate webhook)."""
    entry = WhatsAppMessage(
        provider_message_id=provider_message_id,
        direction=direction,
        wa_id=wa_id,
        phone_number_id=phone_number_id,
        payload=payload,
    )
    db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True


async def handle_webhook_payload(db: Session, payload: dict) -> None:
    settings = get_settings()

    for message in _extract_inbound_messages(payload):
        if message["type"] != "text" or not message["message_id"]:
            continue

        is_new = _log_message(
            db,
            provider_message_id=message["message_id"],
            direction="in",
            wa_id=message["wa_id"],
            phone_number_id=message["phone_number_id"],
            payload=message,
        )
        if not is_new:
            continue
        db.commit()

        if message["wa_id"] in settings.admin_wa_ids:
            outbound = runs_service.process_admin_message(db, message["wa_id"], message["text"])
        else:
            outbound = runs_service.process_buyer_message(db, message["wa_id"], message["text"])
        db.commit()

        for out_message in outbound:
            await client.send_text_message(
                out_message.to, out_message.text, phone_number_id=message["phone_number_id"]
            )
            _log_message(
                db,
                provider_message_id=f"out-{uuid4()}",
                direction="out",
                wa_id=out_message.to,
                phone_number_id=message["phone_number_id"],
                payload={"text": out_message.text},
            )
        db.commit()
