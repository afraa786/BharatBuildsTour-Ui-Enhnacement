from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class InboundMessageType(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    BUTTON = "button"
    VIDEO = "video"
    STICKER = "sticker"
    UNKNOWN = "unknown"


class OutboundMessageType(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    STICKER = "sticker"


class OutputMode(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    DOCUMENT = "document"
    IMAGE = "image"


class ProcessingStatus(StrEnum):
    RECEIVED = "received"
    NEEDS_ENRICHMENT = "needs_enrichment"
    READY = "ready"


class MessageAttachment(BaseModel):
    kind: str
    media_id: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InboundMessageEnvelope(BaseModel):
    provider_message_id: str
    channel: str = "whatsapp"
    direction: str = "in"
    wa_id: str
    phone_number_id: str | None = None
    buyer_name: str | None = None
    content_type: InboundMessageType = InboundMessageType.UNKNOWN
    text: str = ""
    requested_output_mode: OutputMode | None = None
    attachments: list[MessageAttachment] = Field(default_factory=list)
    interactive_payload: dict[str, Any] | None = None
    processing_status: ProcessingStatus = ProcessingStatus.RECEIVED
    raw_payload: dict[str, Any] = Field(default_factory=dict)
