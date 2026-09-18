from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.whatsapp import dispatch
from app.modules.whatsapp.routing import (
    RoutingError,
    WhatsAppExperience,
    WhatsAppRoutingContext,
    resolve_routing_context,
)


def test_customer_experience_never_falls_through_to_legacy_handler(monkeypatch) -> None:
    business_id = uuid4()
    context = WhatsAppRoutingContext(
        "meta_whatsapp", "number-b", business_id, WhatsAppExperience.CUSTOMER_COMMERCE
    )
    observed = []
    monkeypatch.setattr(
        dispatch,
        "customer_commerce_handler",
        lambda db, ctx, message: observed.append((ctx, message)) or [],
    )
    monkeypatch.setattr(
        dispatch.runs_service,
        "process_buyer_message",
        lambda *_: pytest.fail("legacy buyer path called"),
    )
    assert (
        dispatch.dispatch_inbound_message(
            object(),
            context,
            {"wa_id": "same-sender", "text": "hello"},
            admin_wa_ids=set(),
            vendor_wa_ids=set(),
        )
        == []
    )
    assert observed[0][0].business_id == business_id


def test_same_sender_isolated_by_receiving_number(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        dispatch,
        "customer_commerce_handler",
        lambda db, ctx, message: (
            calls.append((ctx.phone_number_id, ctx.experience, message["wa_id"])) or []
        ),
    )
    customer = WhatsAppRoutingContext(
        "meta_whatsapp", "number-b", uuid4(), WhatsAppExperience.CUSTOMER_COMMERCE
    )
    dispatch.dispatch_inbound_message(
        object(),
        customer,
        {"wa_id": "shared-sender", "text": "hi"},
        admin_wa_ids={"shared-sender"},
        vendor_wa_ids=set(),
    )
    assert calls == [("number-b", WhatsAppExperience.CUSTOMER_COMMERCE, "shared-sender")]


def test_unknown_or_disabled_binding_fails_closed() -> None:
    db = SimpleNamespace(scalar=lambda _: None)
    with pytest.raises(RoutingError):
        resolve_routing_context(db, "unknown-number")
    with pytest.raises(RoutingError):
        resolve_routing_context(db, None)
