import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


async def send_text_message(to: str, text: str, phone_number_id: str | None = None) -> None:
    settings = get_settings()
    credentials = settings.whatsapp_number_credentials
    target_phone_number_id = phone_number_id or settings.whatsapp_biz_phone_number_id
    entry = credentials.get(target_phone_number_id)
    if entry is None:
        return
    sending_phone_number_id, access_token = entry

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{sending_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "text": {"body": text},
            },
        )
        if response.status_code >= 400:
            logger.error(
                "whatsapp send failed to=%s status=%s body=%s",
                to,
                response.status_code,
                response.text,
            )
