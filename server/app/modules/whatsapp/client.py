import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


def build_message_payload(
    *,
    to: str,
    message_type: str = "text",
    text: str | None = None,
    media_id: str | None = None,
    link: str | None = None,
    caption: str | None = None,
    filename: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    name: str | None = None,
    address: str | None = None,
    contacts: list[dict[str, Any]] | None = None,
    interactive: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": message_type,
    }

    if message_type == "text":
        payload["text"] = {"body": text or ""}
    elif message_type in {"audio", "image", "video", "sticker"}:
        body: dict[str, Any] = {"id": media_id} if media_id else {"link": link}
        if caption and message_type in {"image", "video"}:
            body["caption"] = caption
        payload[message_type] = body
    elif message_type == "document":
        body = {"id": media_id} if media_id else {"link": link}
        if caption:
            body["caption"] = caption
        if filename:
            body["filename"] = filename
        payload["document"] = body
    elif message_type == "location":
        payload["location"] = {
            "latitude": latitude,
            "longitude": longitude,
            "name": name,
            "address": address,
        }
    elif message_type == "contacts":
        payload["contacts"] = contacts or []
    elif message_type == "interactive":
        payload["interactive"] = interactive or {}
    else:
        raise ValueError(f"Unsupported WhatsApp message type: {message_type}")

    return payload


async def send_message(
    *,
    to: str,
    phone_number_id: str | None = None,
    message_type: str = "text",
    text: str | None = None,
    media_id: str | None = None,
    link: str | None = None,
    caption: str | None = None,
    filename: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    name: str | None = None,
    address: str | None = None,
    contacts: list[dict[str, Any]] | None = None,
    interactive: dict[str, Any] | None = None,
) -> None:
    settings = get_settings()
    credentials = settings.whatsapp_number_credentials
    target_phone_number_id = phone_number_id or settings.whatsapp_biz_phone_number_id
    entry = credentials.get(target_phone_number_id)
    if entry is None:
        return
    sending_phone_number_id, access_token = entry

    payload = build_message_payload(
        to=to,
        message_type=message_type,
        text=text,
        media_id=media_id,
        link=link,
        caption=caption,
        filename=filename,
        latitude=latitude,
        longitude=longitude,
        name=name,
        address=address,
        contacts=contacts,
        interactive=interactive,
    )

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        response = await http_client.post(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{sending_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        )
        if response.status_code >= 400:
            logger.error(
                "whatsapp send failed to=%s status=%s body=%s",
                to,
                response.status_code,
                response.text,
            )


async def send_text_message(to: str, text: str, phone_number_id: str | None = None) -> None:
    await send_message(
        to=to,
        text=text,
        phone_number_id=phone_number_id,
        message_type="text",
    )


async def mark_read_with_typing(message_id: str, phone_number_id: str | None = None) -> None:
    """Marks the inbound message read and shows the WhatsApp typing bubble.

    The indicator auto-dismisses after ~25s or as soon as the reply is sent,
    whichever comes first -- call this right before doing any slow work
    (LLM calls, transcription) so the sender sees something immediately.
    """
    settings = get_settings()
    credentials = settings.whatsapp_number_credentials
    target_phone_number_id = phone_number_id or settings.whatsapp_biz_phone_number_id
    entry = credentials.get(target_phone_number_id)
    if entry is None:
        return
    sending_phone_number_id, access_token = entry

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        response = await http_client.post(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{sending_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
                "typing_indicator": {"type": "text"},
            },
        )
        if response.status_code >= 400:
            logger.error(
                "mark-read/typing indicator failed message_id=%s status=%s body=%s",
                message_id,
                response.status_code,
                response.text,
            )
