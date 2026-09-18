"""Real audio in/out over WhatsApp: download+transcribe inbound voice notes,
synthesize+upload outbound speech. Every failure here degrades gracefully
(returns None) -- callers fall back to their existing text-only behavior,
so a Whisper/TTS/media-API outage never blocks the core text flow.
"""

import logging

import httpx
from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


async def download_media(media_id: str, access_token: str) -> tuple[bytes, str] | None:
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        meta_response = await http_client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if meta_response.status_code >= 400:
            logger.error(
                "media metadata fetch failed id=%s status=%s", media_id, meta_response.status_code
            )
            return None

        meta = meta_response.json()
        url = meta.get("url")
        mime_type = meta.get("mime_type", "audio/ogg")
        if not url:
            return None

        file_response = await http_client.get(
            url, headers={"Authorization": f"Bearer {access_token}"}
        )
        if file_response.status_code >= 400:
            logger.error(
                "media download failed id=%s status=%s", media_id, file_response.status_code
            )
            return None
        return file_response.content, mime_type


async def upload_media(
    data: bytes, mime_type: str, phone_number_id: str, access_token: str
) -> str | None:
    filename = "reply.mp3" if "mp3" in mime_type or "mpeg" in mime_type else "reply.ogg"
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        response = await http_client.post(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/media",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, data, mime_type)},
        )
        if response.status_code >= 400:
            logger.error(
                "media upload failed status=%s body=%s", response.status_code, response.text
            )
            return None
        return response.json().get("id")


def _mime_to_extension(mime_type: str) -> str:
    if "ogg" in mime_type:
        return "ogg"
    if "mp3" in mime_type or "mpeg" in mime_type:
        return "mp3"
    if "wav" in mime_type:
        return "wav"
    return "m4a"


def transcribe(data: bytes, mime_type: str) -> str | None:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)
        extension = _mime_to_extension(mime_type)
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=(f"audio.{extension}", data, mime_type),
        )
        text = (response.text or "").strip()
        return text or None
    except Exception:
        logger.exception("transcription failed, falling back to non-text acknowledgement")
        return None


def synthesize(text: str) -> bytes | None:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key or not text:
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        return response.content
    except Exception:
        logger.exception("speech synthesis failed, falling back to text reply")
        return None
