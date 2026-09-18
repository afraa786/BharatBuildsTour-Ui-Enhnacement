from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.modules.whatsapp import client
from app.modules.whatsapp import service as whatsapp_service
from app.modules.whatsapp.routing import WhatsAppExperience, WhatsAppRoutingContext
from app.modules.whatsapp.service import (
    ADMIN_BOT_UNAUTHORIZED_TEXT,
    _extract_inbound_messages,
    handle_webhook_payload,
)


class FakeDb:
    def add(self, entry):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    @contextmanager
    def begin_nested(self):
        yield


def _fake_owner_manager_context(db, phone_number_id, *, provider="meta_whatsapp"):
    return WhatsAppRoutingContext(
        provider, phone_number_id, uuid4(), WhatsAppExperience.OWNER_MANAGER
    )


def _single_text_payload(*, phone_number_id: str, wa_id: str, text: str) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Sender"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{wa_id}",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_extract_inbound_messages_supports_multiple_whatsapp_types() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "pn-1"},
                            "contacts": [
                                {"wa_id": "buyer-1", "profile": {"name": "Asha"}},
                            ],
                            "messages": [
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.text.1",
                                    "type": "text",
                                    "text": {"body": "send summary in audio"},
                                },
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.audio.1",
                                    "type": "audio",
                                    "audio": {
                                        "id": "media-a1",
                                        "mime_type": "audio/ogg",
                                        "voice": True,
                                    },
                                },
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.image.1",
                                    "type": "image",
                                    "image": {
                                        "id": "media-i1",
                                        "mime_type": "image/jpeg",
                                        "caption": "Need this in blue",
                                    },
                                },
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.doc.1",
                                    "type": "document",
                                    "document": {
                                        "id": "media-d1",
                                        "mime_type": "application/pdf",
                                        "filename": "rfq.pdf",
                                        "caption": "latest RFQ",
                                    },
                                },
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.loc.1",
                                    "type": "location",
                                    "location": {
                                        "latitude": 12.97,
                                        "longitude": 77.59,
                                        "name": "Indiranagar",
                                        "address": "Bengaluru",
                                    },
                                },
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.contacts.1",
                                    "type": "contacts",
                                    "contacts": [
                                        {
                                            "name": {"formatted_name": "Ravi Vendor"},
                                            "phones": [{"phone": "+91"}],
                                        }
                                    ],
                                },
                                {
                                    "from": "buyer-1",
                                    "id": "wamid.interactive.1",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": "accept-1", "title": "Accept quote"},
                                    },
                                },
                            ],
                        }
                    }
                ]
            }
        ]
    }

    messages = list(_extract_inbound_messages(payload))

    assert [m["type"] for m in messages] == [
        "text",
        "audio",
        "image",
        "document",
        "location",
        "contacts",
        "interactive",
    ]
    assert messages[0]["requested_output_mode"] == "audio"
    assert messages[1]["media_id"] == "media-a1"
    assert messages[1]["voice"] is True
    assert messages[2]["text"] == "Need this in blue"
    assert messages[3]["filename"] == "rfq.pdf"
    assert messages[4]["location_name"] == "Indiranagar"
    assert messages[5]["contacts_count"] == 1
    assert messages[6]["text"] == "Accept quote"


def test_build_message_payload_supports_audio_document_and_location() -> None:
    audio_payload = client.build_message_payload(
        to="buyer-1",
        message_type="audio",
        link="https://example.com/summary.ogg",
    )
    document_payload = client.build_message_payload(
        to="buyer-1",
        message_type="document",
        link="https://example.com/invoice.pdf",
        caption="Invoice ready",
        filename="invoice.pdf",
    )
    location_payload = client.build_message_payload(
        to="buyer-1",
        message_type="location",
        latitude=12.97,
        longitude=77.59,
        name="Warehouse",
        address="Bengaluru",
    )

    assert audio_payload["audio"]["link"] == "https://example.com/summary.ogg"
    assert document_payload["document"]["filename"] == "invoice.pdf"
    assert document_payload["document"]["caption"] == "Invoice ready"
    assert location_payload["location"]["latitude"] == 12.97
    assert location_payload["location"]["name"] == "Warehouse"


@pytest.mark.anyio
async def test_admin_bot_rejects_non_admin_order_flow(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_WHATSAPP_PHONE_NUMBER_IDS", "admin-pn")
    monkeypatch.setenv("ADMIN_WHATSAPP_NUMBERS", "owner-1")
    get_settings.cache_clear()
    sent: list[dict] = []

    async def fake_mark_read(message_id, phone_number_id):
        pass

    async def fake_send_message(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(client, "mark_read_with_typing", fake_mark_read)
    monkeypatch.setattr(client, "send_message", fake_send_message)
    monkeypatch.setattr(whatsapp_service, "resolve_routing_context", _fake_owner_manager_context)

    await handle_webhook_payload(
        FakeDb(),
        _single_text_payload(
            phone_number_id="admin-pn",
            wa_id="buyer-1",
            text="order 20 led bulbs",
        ),
    )

    assert sent[0]["to"] == "buyer-1"
    assert sent[0]["text"] == ADMIN_BOT_UNAUTHORIZED_TEXT


@pytest.mark.anyio
async def test_admin_bot_admin_sender_stays_manager_scoped(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_WHATSAPP_PHONE_NUMBER_IDS", "admin-pn")
    monkeypatch.setenv("ADMIN_WHATSAPP_NUMBERS", "owner-1")
    get_settings.cache_clear()
    sent: list[dict] = []

    async def fake_mark_read(message_id, phone_number_id):
        pass

    async def fake_send_message(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(client, "mark_read_with_typing", fake_mark_read)
    monkeypatch.setattr(client, "send_message", fake_send_message)
    monkeypatch.setattr(whatsapp_service, "resolve_routing_context", _fake_owner_manager_context)

    await handle_webhook_payload(
        FakeDb(),
        _single_text_payload(
            phone_number_id="admin-pn",
            wa_id="owner-1",
            text="order 20 led bulbs",
        ),
    )

    assert sent[0]["to"] == "owner-1"
    assert "StockAware Manager" in sent[0]["text"]
    assert "don't place buyer orders" in sent[0]["text"]
