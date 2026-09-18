from app.modules.whatsapp import client
from app.modules.whatsapp.service import _extract_inbound_messages


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
