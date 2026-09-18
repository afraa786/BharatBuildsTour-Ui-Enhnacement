from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.runs import service as runs_service
from app.modules.runs.intent_router import ActorType, route_message
from app.modules.whatsapp import audio, client
from app.modules.whatsapp.dispatch import (
    dispatch_inbound_message,
    ensure_experience_handler_available,
)
from app.modules.whatsapp.models import WhatsAppMessage, WhatsAppMessageStatus
from app.modules.whatsapp.routing import WhatsAppExperience, resolve_routing_context

TEXTUAL_MESSAGE_TYPES = {
    "text",
    "interactive",
    "button",
    "image",
    "video",
    "document",
}

ADMIN_BOT_UNAUTHORIZED_TEXT = (
    "This is the StockAware Manager line for the owner/admin team. "
    "Please message the customer ordering number for quotes or orders."
)


def _detect_requested_output_mode(text: str) -> str | None:
    normalized = text.casefold().strip()
    audio_tokens = ("audio", "voice", "voice note", "audio me", "audio mein")
    if any(token in normalized for token in audio_tokens):
        return "audio"
    if any(token in normalized for token in ("pdf", "document", "doc", "invoice pdf")):
        return "document"
    if any(token in normalized for token in ("image", "photo", "pic", "picture")):
        return "image"
    return None


def _extract_text_content(message: dict) -> tuple[str, dict]:
    message_type = message.get("type")
    if message_type == "text":
        text = message.get("text", {}).get("body", "")
        return text, {"text_body": text}
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        reply_type = interactive.get("type")
        if reply_type == "button_reply":
            reply = interactive.get("button_reply", {})
            title = reply.get("title", "")
            return title, {
                "interactive_type": reply_type,
                "interactive_reply_id": reply.get("id"),
                "interactive_reply_title": title,
            }
        if reply_type == "list_reply":
            reply = interactive.get("list_reply", {})
            title = reply.get("title", "")
            return title, {
                "interactive_type": reply_type,
                "interactive_reply_id": reply.get("id"),
                "interactive_reply_title": title,
                "interactive_reply_description": reply.get("description"),
            }
        return "", {"interactive_type": reply_type}
    if message_type == "button":
        button = message.get("button", {})
        text = button.get("text", "")
        return text, {"button_payload": button.get("payload"), "button_text": text}
    if message_type in {"image", "video", "document"}:
        body = message.get(message_type, {})
        caption = body.get("caption", "")
        return caption, {
            "media_id": body.get("id"),
            "mime_type": body.get("mime_type"),
            "caption": caption,
            "filename": body.get("filename"),
            "sha256": body.get("sha256"),
        }
    if message_type == "audio":
        body = message.get("audio", {})
        return "", {
            "media_id": body.get("id"),
            "mime_type": body.get("mime_type"),
            "sha256": body.get("sha256"),
            "voice": body.get("voice", False),
        }
    if message_type == "sticker":
        body = message.get("sticker", {})
        return "", {
            "media_id": body.get("id"),
            "mime_type": body.get("mime_type"),
            "animated": body.get("animated", False),
        }
    if message_type == "location":
        body = message.get("location", {})
        summary = " ".join(filter(None, [body.get("name"), body.get("address")]))
        return summary, {
            "latitude": body.get("latitude"),
            "longitude": body.get("longitude"),
            "location_name": body.get("name"),
            "location_address": body.get("address"),
        }
    if message_type == "contacts":
        contacts = message.get("contacts", [])
        names = [contact.get("name", {}).get("formatted_name", "") for contact in contacts]
        return " ".join(filter(None, names)), {
            "contacts_count": len(contacts),
            "contacts": contacts,
        }
    return "", {}


def _extract_inbound_messages(payload: dict) -> Iterator[dict]:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            contacts = {
                c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])
            }
            for message in value.get("messages", []):
                text, extra = _extract_text_content(message)
                yield {
                    "phone_number_id": phone_number_id,
                    "wa_id": message.get("from"),
                    "buyer_name": contacts.get(message.get("from")),
                    "message_id": message.get("id"),
                    "type": message.get("type"),
                    "text": text,
                    "requested_output_mode": _detect_requested_output_mode(text),
                    **extra,
                }


def _extract_status_events(payload: dict) -> Iterator[dict]:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            for status_event in value.get("statuses", []):
                provider_message_id = status_event.get("id")
                status_value = status_event.get("status")
                if not provider_message_id or status_value not in {
                    "sent",
                    "delivered",
                    "read",
                    "failed",
                }:
                    continue
                occurred_at = None
                try:
                    occurred_at = datetime.fromtimestamp(int(status_event["timestamp"]), UTC)
                except (KeyError, TypeError, ValueError, OverflowError):
                    pass
                yield {
                    "provider_message_id": provider_message_id,
                    "phone_number_id": phone_number_id,
                    "recipient_wa_id": status_event.get("recipient_id"),
                    "status": status_value,
                    "occurred_at": occurred_at,
                    "payload": status_event,
                }


def _log_status_event(db: Session, event: dict) -> bool:
    try:
        with db.begin_nested():
            db.add(WhatsAppMessageStatus(**event))
            db.flush()
    except IntegrityError:
        return False
    return True


def _log_message(
    db: Session,
    provider_message_id: str,
    direction: str,
    wa_id: str,
    phone_number_id: str | None,
    payload: dict,
    business_id=None,
) -> bool:
    """Returns False if this provider_message_id was already logged (duplicate webhook)."""
    try:
        with db.begin_nested():
            db.add(
                WhatsAppMessage(
                    provider_message_id=provider_message_id,
                    direction=direction,
                    wa_id=wa_id,
                    phone_number_id=phone_number_id,
                    business_id=business_id,
                    payload=payload,
                )
            )
            db.flush()
    except IntegrityError:
        return False
    return True


def _non_text_acknowledgement(message: dict) -> str:
    message_type = message["type"]
    if message_type == "audio":
        return (
            "I received your audio note. Send a short text too, "
            "or connect transcription for full voice handling."
        )
    if message_type == "image":
        return (
            "I received your image. Add quantity or a short note "
            "if you want me to prepare a quote from it."
        )
    if message_type == "document":
        return (
            "I received your document. I can use the caption "
            "and attached file context for the next step."
        )
    if message_type == "location":
        return "Location received. I can use it for delivery or pickup planning."
    if message_type == "contacts":
        return "Contact received. I can use it for vendor or buyer follow-up once linked to a run."
    if message_type == "video":
        return "Video received. Add a short caption or text so I know what action to take."
    if message_type == "sticker":
        return "Sticker received. Send a short text if you want me to take an action."
    return "I received your message. Send a short text if you want me to take a specific action."


async def handle_webhook_payload(db: Session, payload: dict) -> None:
    settings = get_settings()
    for status_event in _extract_status_events(payload):
        # Delivery callbacks are tenant-scoped by the same trusted receiving number.
        context = resolve_routing_context(db, status_event["phone_number_id"])
        _log_status_event(db, {**status_event, "business_id": context.business_id})
    db.commit()

    for message in _extract_inbound_messages(payload):
        if not message["message_id"]:
            continue

        # Resolve before any network or business action. Message content cannot influence this.
        context = resolve_routing_context(db, message["phone_number_id"])
        ensure_experience_handler_available(context)
        is_new = _log_message(
            db,
            provider_message_id=message["message_id"],
            direction="in",
            wa_id=message["wa_id"],
            phone_number_id=message["phone_number_id"],
            payload=message,
            business_id=context.business_id,
        )
        if not is_new:
            continue
        db.commit()

        await client.mark_read_with_typing(message["message_id"], message["phone_number_id"])

        if message["type"] == "audio" and message.get("media_id"):
            creds = settings.whatsapp_number_credentials.get(message["phone_number_id"])
            if creds:
                _, access_token = creds
                downloaded = await audio.download_media(message["media_id"], access_token)
                if downloaded:
                    audio_bytes, mime_type = downloaded
                    transcript = audio.transcribe(audio_bytes, mime_type)
                    if transcript:
                        message["text"] = transcript
                        message["type"] = "text"
                        message["requested_output_mode"] = (
                            message["requested_output_mode"] or "audio"
                        )

        is_admin_sender = message["wa_id"] in settings.admin_wa_ids
        is_vendor_sender = message["wa_id"] in settings.vendor_wa_ids
        is_admin_bot = message["phone_number_id"] in settings.admin_phone_number_ids
        business_id = settings.whatsapp_business_by_phone_number_id.get(message["phone_number_id"])

        decision = route_message(
            message["text"],
            actor_hint=(
                ActorType.ADMIN
                if is_admin_sender
                else ActorType.VENDOR
                if is_vendor_sender
                else None
            ),
            wa_id=message["wa_id"],
            admin_wa_ids=settings.admin_wa_ids,
            vendor_wa_ids=settings.vendor_wa_ids,
        )
        decision_actor = decision.actor
        decision_intent = decision.intent
        decision_actor_source = decision.actor_source
        decision_matched_rule = decision.matched_rule
        decision_requires_exact_run_id = decision.requires_exact_run_id
        if (
            context.experience is WhatsAppExperience.OWNER_MANAGER
            and message["type"] not in TEXTUAL_MESSAGE_TYPES
            and not message["text"]
        ):
            outbound = [
                runs_service.OutboundMessage(
                    to=message["wa_id"],
                    text=_non_text_acknowledgement(message),
                )
            ]
        else:
            if context.experience is WhatsAppExperience.CUSTOMER_COMMERCE:
                outbound = dispatch_inbound_message(
                    db,
                    context,
                    message,
                    admin_wa_ids=settings.admin_wa_ids,
                    vendor_wa_ids=settings.vendor_wa_ids,
                )
            elif is_admin_bot and not is_admin_sender:
                outbound = [
                    runs_service.OutboundMessage(
                        to=message["wa_id"],
                        text=ADMIN_BOT_UNAUTHORIZED_TEXT,
                    )
                ]
                decision = route_message(
                    message["text"],
                    actor_hint=ActorType.ADMIN,
                    wa_id=message["wa_id"],
                )
                decision_actor = decision.actor
                decision_intent = decision.intent
                decision_actor_source = decision.actor_source
                decision_matched_rule = decision.matched_rule
                decision_requires_exact_run_id = decision.requires_exact_run_id
            elif is_admin_sender or decision.actor is ActorType.ADMIN:
                outbound = runs_service.process_admin_message(
                    db,
                    message["wa_id"],
                    message["text"],
                    phone_number_id=message["phone_number_id"],
                )
            elif decision.actor is ActorType.VENDOR:
                outbound = runs_service.process_vendor_message(
                    db, message["wa_id"], message["text"]
                )
            else:
                outbound = runs_service.process_buyer_message(
                    db,
                    message["wa_id"],
                    message["text"],
                    phone_number_id=message["phone_number_id"],
                    interactive_reply_id=message.get("interactive_reply_id"),
                    business_id=business_id,
                )

        db.commit()

        for out_message in outbound:
            send_kwargs = {
                "to": out_message.to,
                "phone_number_id": message["phone_number_id"],
                "message_type": getattr(out_message, "message_type", "text"),
                "text": getattr(out_message, "text", None),
                "media_id": getattr(out_message, "media_id", None),
                "link": getattr(out_message, "link", None),
                "caption": getattr(out_message, "caption", None),
                "filename": getattr(out_message, "filename", None),
                "latitude": getattr(out_message, "latitude", None),
                "longitude": getattr(out_message, "longitude", None),
                "name": getattr(out_message, "name", None),
                "address": getattr(out_message, "address", None),
                "contacts": getattr(out_message, "contacts", None),
                "interactive": getattr(out_message, "interactive", None),
            }

            sent_as_audio = False
            if (
                message.get("requested_output_mode") == "audio"
                and send_kwargs["message_type"] == "text"
                and send_kwargs["text"]
            ):
                creds = settings.whatsapp_number_credentials.get(message["phone_number_id"])
                if creds:
                    _, access_token = creds
                    audio_bytes = audio.synthesize(send_kwargs["text"])
                    if audio_bytes:
                        uploaded_media_id = await audio.upload_media(
                            audio_bytes, "audio/mpeg", message["phone_number_id"], access_token
                        )
                        if uploaded_media_id:
                            send_kwargs["message_type"] = "audio"
                            send_kwargs["media_id"] = uploaded_media_id
                            sent_as_audio = True

            await client.send_message(**send_kwargs)
            _log_message(
                db,
                provider_message_id=f"out-{uuid4()}",
                direction="out",
                wa_id=out_message.to,
                phone_number_id=message["phone_number_id"],
                business_id=context.business_id,
                payload={
                    "text": out_message.text,
                    "message_type": send_kwargs["message_type"],
                    "sent_as_audio": sent_as_audio,
                    "actor": decision_actor.value,
                    "intent": decision_intent.value,
                    "actor_source": decision_actor_source,
                    "matched_rule": decision_matched_rule,
                    "requires_exact_run_id": decision_requires_exact_run_id,
                    "business_id": str(context.business_id),
                    "experience": context.experience.value,
                },
            )
        db.commit()
