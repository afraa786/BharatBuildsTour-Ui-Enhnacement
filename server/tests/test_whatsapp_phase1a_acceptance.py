import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.modules.runs.service import OutboundMessage
from app.modules.whatsapp import dispatch, service
from app.modules.whatsapp import router as whatsapp_router
from app.modules.whatsapp.routing import (
    RoutingError,
    WhatsAppExperience,
    WhatsAppRoutingContext,
    resolve_routing_context,
)

APP_SECRET = "synthetic-meta-app-secret"  # pragma: allowlist secret


def _payload(phone_number_id: str = "number-a", message_id: str = "wamid.phase1a.1") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-test",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+910000000000",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"wa_id": "shared-sender", "profile": {"name": "Test Sender"}}
                            ],
                            "messages": [
                                {
                                    "from": "shared-sender",
                                    "id": message_id,
                                    "timestamp": "1760000000",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _signed_headers(raw_body: bytes) -> dict[str, str]:
    digest = hmac.new(APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={digest}",
    }


@pytest.fixture
def webhook_client(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_valid_meta_signature_accepts_exact_raw_body(webhook_client, monkeypatch) -> None:
    calls = []

    async def handler(db, payload):
        calls.append(payload)

    monkeypatch.setattr(whatsapp_router, "handle_webhook_payload", handler)
    raw = json.dumps(_payload(), separators=(",", ":")).encode()
    response = webhook_client.post("/webhook/whatsapp", content=raw, headers=_signed_headers(raw))
    assert response.status_code == 200
    assert calls == [_payload()]


def test_invalid_and_missing_meta_signatures_are_rejected(webhook_client, monkeypatch) -> None:
    async def forbidden_handler(*_):
        pytest.fail("unsigned payload reached handler")

    monkeypatch.setattr(whatsapp_router, "handle_webhook_payload", forbidden_handler)
    raw = json.dumps(_payload(), separators=(",", ":")).encode()
    invalid = webhook_client.post(
        "/webhook/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
    )
    missing = webhook_client.post("/webhook/whatsapp", content=raw)
    assert invalid.status_code == 401
    assert missing.status_code == 401


def test_get_webhook_verification_behavior_is_preserved(webhook_client, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_TEST_VERIFY_TOKEN", "synthetic-verify-token")
    get_settings.cache_clear()
    response = webhook_client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "synthetic-verify-token",
            "hub.challenge": "challenge-value",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge-value"


def test_unknown_number_returns_403_without_dispatch(webhook_client, monkeypatch) -> None:
    async def handler(*_):
        raise RoutingError("unknown")

    monkeypatch.setattr(whatsapp_router, "handle_webhook_payload", handler)
    raw = json.dumps(_payload("unknown-number"), separators=(",", ":")).encode()
    response = webhook_client.post("/webhook/whatsapp", content=raw, headers=_signed_headers(raw))
    assert response.status_code == 403


class _RoutingDb:
    def __init__(self, binding=None, business_exists=True):
        self.binding = binding
        self.business_exists = business_exists

    def scalar(self, _statement):
        return self.binding if self.binding is not None and self.binding.enabled else None

    def get(self, _model, _business_id):
        return object() if self.business_exists else None


def _binding(experience: str, *, enabled: bool = True, business_id=None):
    return SimpleNamespace(
        enabled=enabled,
        business_id=business_id or uuid4(),
        experience=experience,
    )


def test_unknown_disabled_missing_business_and_unsupported_bindings_fail_closed() -> None:
    with pytest.raises(RoutingError):
        resolve_routing_context(_RoutingDb(), "unknown")
    with pytest.raises(RoutingError):
        resolve_routing_context(
            _RoutingDb(_binding(WhatsAppExperience.OWNER_MANAGER, enabled=False)),
            "disabled",
        )
    with pytest.raises(RoutingError):
        resolve_routing_context(
            _RoutingDb(_binding(WhatsAppExperience.OWNER_MANAGER), business_exists=False),
            "orphaned",
        )
    with pytest.raises(RoutingError):
        resolve_routing_context(_RoutingDb(_binding("unsupported")), "unsupported")


def test_number_a_dispatches_existing_owner_manager(monkeypatch) -> None:
    context = WhatsAppRoutingContext(
        "meta_whatsapp", "number-a", uuid4(), WhatsAppExperience.OWNER_MANAGER
    )
    calls = []
    monkeypatch.setattr(
        dispatch.runs_service,
        "process_admin_message",
        lambda db, wa_id, text, phone_number_id: (
            calls.append((db, wa_id, text, phone_number_id))
            or [OutboundMessage(to=wa_id, text="owner reply")]
        ),
    )
    db = object()
    result = dispatch.dispatch_inbound_message(
        db,
        context,
        {"wa_id": "shared-sender", "text": "show open quotes"},
        admin_wa_ids={"shared-sender"},
        vendor_wa_ids=set(),
    )
    assert result[0].text == "owner reply"
    assert calls == [(db, "shared-sender", "show open quotes", "number-a")]


def test_number_b_dispatches_only_customer_commerce(monkeypatch) -> None:
    business_id = uuid4()
    context = WhatsAppRoutingContext(
        "meta_whatsapp", "number-b", business_id, WhatsAppExperience.CUSTOMER_COMMERCE
    )
    calls = []
    monkeypatch.setattr(
        dispatch,
        "customer_commerce_handler",
        lambda db, ctx, message: calls.append((db, ctx, message)) or [],
    )
    monkeypatch.setattr(
        dispatch.runs_service,
        "process_buyer_message",
        lambda *_args, **_kwargs: pytest.fail("Number B reached legacy mock RFQ"),
    )
    db = object()
    message = {"wa_id": "shared-sender", "text": "show products"}
    assert (
        dispatch.dispatch_inbound_message(
            db,
            context,
            message,
            admin_wa_ids={"shared-sender"},
            vendor_wa_ids=set(),
        )
        == []
    )
    assert calls == [(db, context, message)]


def test_same_sender_on_two_numbers_remains_isolated(monkeypatch) -> None:
    owner_context = WhatsAppRoutingContext(
        "meta_whatsapp", "number-a", uuid4(), WhatsAppExperience.OWNER_MANAGER
    )
    commerce_context = WhatsAppRoutingContext(
        "meta_whatsapp", "number-b", uuid4(), WhatsAppExperience.CUSTOMER_COMMERCE
    )
    calls = []
    monkeypatch.setattr(
        dispatch.runs_service,
        "process_admin_message",
        lambda *_args, **_kwargs: calls.append("owner") or [],
    )
    monkeypatch.setattr(
        dispatch,
        "customer_commerce_handler",
        lambda *_args, **_kwargs: calls.append("commerce") or [],
    )
    message = {"wa_id": "shared-sender", "text": "hello"}
    for context in (owner_context, commerce_context):
        dispatch.dispatch_inbound_message(
            object(),
            context,
            message,
            admin_wa_ids={"shared-sender"},
            vendor_wa_ids=set(),
        )
    assert calls == ["owner", "commerce"]


def test_sender_cannot_override_business_experience_or_cross_tenant(monkeypatch) -> None:
    trusted_business_id = uuid4()
    attacker_business_id = uuid4()
    context = resolve_routing_context(
        _RoutingDb(_binding("customer_commerce", business_id=trusted_business_id)),
        "number-b",
    )
    observed = []
    monkeypatch.setattr(
        dispatch,
        "customer_commerce_handler",
        lambda db, ctx, message: observed.append((ctx, message)) or [],
    )
    message = {
        "wa_id": "sender",
        "text": "hello",
        "business_id": str(attacker_business_id),
        "experience": "owner_manager",
    }
    dispatch.dispatch_inbound_message(
        object(), context, message, admin_wa_ids=set(), vendor_wa_ids=set()
    )
    assert observed[0][0].business_id == trusted_business_id
    assert observed[0][0].experience is WhatsAppExperience.CUSTOMER_COMMERCE
    assert observed[0][1] is message


class _WebhookDb:
    def commit(self):
        pass


def test_duplicate_provider_message_id_does_not_redispatch(monkeypatch) -> None:
    seen = set()
    dispatches = []
    context = WhatsAppRoutingContext(
        "meta_whatsapp", "number-b", uuid4(), WhatsAppExperience.CUSTOMER_COMMERCE
    )

    def claim(_db, provider_message_id, **_kwargs):
        if provider_message_id in seen:
            return False
        seen.add(provider_message_id)
        return True

    async def no_network(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_log_message", claim)
    monkeypatch.setattr(service, "resolve_routing_context", lambda *_args, **_kwargs: context)
    monkeypatch.setattr(service, "ensure_experience_handler_available", lambda _context: None)
    monkeypatch.setattr(service.client, "mark_read_with_typing", no_network)
    monkeypatch.setattr(
        service,
        "dispatch_inbound_message",
        lambda *_args, **_kwargs: dispatches.append("called") or [],
    )
    payload = _payload("number-b", "wamid.duplicate")
    import asyncio

    asyncio.run(service.handle_webhook_payload(_WebhookDb(), payload))
    asyncio.run(service.handle_webhook_payload(_WebhookDb(), payload))
    assert dispatches == ["called"]


def test_status_events_are_normalized_without_faking_transitions() -> None:
    payload = _payload()
    value = payload["entry"][0]["changes"][0]["value"]
    value.pop("messages")
    value["statuses"] = [
        {
            "id": "wamid.outbound.1",
            "status": "delivered",
            "timestamp": "1760000000",
            "recipient_id": "shared-sender",
        }
    ]
    events = list(service._extract_status_events(payload))
    assert len(events) == 1
    assert events[0]["status"] == "delivered"
    assert events[0]["phone_number_id"] == "number-a"
    assert events[0]["provider_message_id"] == "wamid.outbound.1"


def test_signed_webhook_end_to_end_number_isolation_and_duplicate(
    webhook_client, monkeypatch
) -> None:
    """No real DB, LLM, or Meta calls; exercise the actual FastAPI route and dispatch."""
    from app.modules.commerce import service as commerce_service

    seen = set()
    calls = []
    business_a, business_b = uuid4(), uuid4()
    contexts = {
        "number-a": WhatsAppRoutingContext(
            "meta_whatsapp", "number-a", business_a, WhatsAppExperience.OWNER_MANAGER
        ),
        "number-b": WhatsAppRoutingContext(
            "meta_whatsapp", "number-b", business_b, WhatsAppExperience.CUSTOMER_COMMERCE
        ),
    }

    def resolve(_db, phone_number_id):
        if phone_number_id not in contexts:
            raise RoutingError("unknown")
        return contexts[phone_number_id]

    def claim(_db, provider_message_id, **_kwargs):
        if provider_message_id in seen:
            return False
        seen.add(provider_message_id)
        return True

    async def no_network(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "resolve_routing_context", resolve)
    monkeypatch.setattr(service, "_log_message", claim)
    monkeypatch.setattr(service.client, "mark_read_with_typing", no_network)
    monkeypatch.setattr(service.client, "send_message", no_network)
    monkeypatch.setattr(
        dispatch.runs_service,
        "process_admin_message",
        lambda _db, wa_id, _text, phone_number_id: (
            calls.append(("owner", phone_number_id, business_a))
            or [OutboundMessage(to=wa_id, text="owner reply")]
        ),
    )
    monkeypatch.setattr(
        commerce_service,
        "process_customer_commerce_message",
        lambda _db, business_id, phone_number_id, wa_id, text_body: (
            calls.append(("commerce", phone_number_id, business_id))
            or [OutboundMessage(to=wa_id, text="commerce reply")]
        ),
    )
    monkeypatch.setenv("ADMIN_WHATSAPP_NUMBERS", "shared-sender")
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: _WebhookDb()

    for phone, message_id in (("number-a", "wamid.a"), ("number-b", "wamid.b")):
        raw = json.dumps(_payload(phone, message_id), separators=(",", ":")).encode()
        first = webhook_client.post("/webhook/whatsapp", content=raw, headers=_signed_headers(raw))
        second = webhook_client.post("/webhook/whatsapp", content=raw, headers=_signed_headers(raw))
        assert first.status_code == 200
        assert second.status_code == 200

    raw_unknown = json.dumps(_payload("number-unknown", "wamid.unknown")).encode()
    rejected = webhook_client.post(
        "/webhook/whatsapp", content=raw_unknown, headers=_signed_headers(raw_unknown)
    )
    assert rejected.status_code == 403
    assert calls == [
        ("owner", "number-a", business_a),
        ("commerce", "number-b", business_b),
    ]
