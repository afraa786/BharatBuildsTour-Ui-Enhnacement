import json
from datetime import UTC, datetime

import httpx
import pytest

from app.modules.payments.service import (
    RazorpayPaymentLinkRequest,
    build_payment_link_payload,
    create_payment_link,
    parse_captured_payment_event,
    verify_razorpay_signature,
)


def _signed_body(body: bytes, secret: str) -> str:
    import hmac
    from hashlib import sha256

    return hmac.new(secret.encode(), body, sha256).hexdigest()


def test_verify_razorpay_signature_accepts_only_exact_hmac() -> None:
    body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_123"}}}}'
    signature = _signed_body(body, "webhook-test-secret")

    assert verify_razorpay_signature(body, signature, "webhook-test-secret") is True
    assert verify_razorpay_signature(body, "0" * 64, "webhook-test-secret") is False


def test_build_payment_link_payload_binds_business_reference_and_amount() -> None:
    request = RazorpayPaymentLinkRequest(
        run_id="RFQ-1042",
        quote_id="QT-1042-V1",
        amount_paise=141600,
        buyer_name="Sharma Electricals",
        buyer_phone="919999999999",
        description="StockAware quote RFQ-1042",
        callback_url="https://stockaware.example/payments/razorpay/callback",
        expires_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    payload = build_payment_link_payload(request)

    assert payload["amount"] == 141600
    assert payload["currency"] == "INR"
    assert payload["reference_id"] == "RFQ-1042:QT-1042-V1"
    assert payload["customer"] == {
        "name": "Sharma Electricals",
        "contact": "919999999999",
    }
    assert payload["notify"] == {"sms": False, "email": False}
    assert payload["callback_url"] == "https://stockaware.example/payments/razorpay/callback"
    assert payload["callback_method"] == "get"
    assert payload["expire_by"] == 1789819200
    assert payload["notes"] == {"run_id": "RFQ-1042", "quote_id": "QT-1042-V1"}


@pytest.mark.anyio
async def test_create_payment_link_posts_to_razorpay_without_leaking_secret() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "plink_test_123",
                "short_url": "https://rzp.io/i/test123",
                "status": "created",
                "reference_id": "RFQ-1042:QT-1042-V1",
                "amount": 141600,
                "currency": "INR",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await create_payment_link(
            client=client,
            request=RazorpayPaymentLinkRequest(
                run_id="RFQ-1042",
                quote_id="QT-1042-V1",
                amount_paise=141600,
                buyer_name="Sharma Electricals",
                buyer_phone="919999999999",
            ),
            key_id="rzp_test_public",
            key_secret="test_secret_do_not_return",
        )

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.razorpay.com/v1/payment_links"
    assert captured["payload"]["amount"] == 141600
    assert captured["payload"]["reference_id"] == "RFQ-1042:QT-1042-V1"
    assert result.provider_link_id == "plink_test_123"
    assert result.payment_url == "https://rzp.io/i/test123"
    assert "test_secret_do_not_return" not in result.model_dump_json()


def test_parse_captured_payment_event_extracts_verified_business_fields() -> None:
    event = {
        "id": "evt_test_123",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "order_id": "order_test_123",
                    "amount": 141600,
                    "currency": "INR",
                    "status": "captured",
                    "captured": True,
                    "notes": {"run_id": "RFQ-1042", "quote_id": "QT-1042-V1"},
                    "created_at": 1797595200,
                }
            }
        },
    }

    parsed = parse_captured_payment_event(event)

    assert parsed.provider_event_id == "evt_test_123"
    assert parsed.provider_payment_id == "pay_test_123"
    assert parsed.provider_order_id == "order_test_123"
    assert parsed.amount_paise == 141600
    assert parsed.currency == "INR"
    assert parsed.run_id == "RFQ-1042"
    assert parsed.quote_id == "QT-1042-V1"
    assert parsed.paid_at == datetime(2026, 12, 18, 12, 0, tzinfo=UTC)


def test_parse_captured_payment_event_rejects_unpaid_or_wrong_currency() -> None:
    failed = {
        "id": "evt_test_124",
        "event": "payment.failed",
        "payload": {"payment": {"entity": {"status": "failed", "currency": "INR"}}},
    }
    wrong_currency = {
        "id": "evt_test_125",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_125",
                    "amount": 100,
                    "currency": "USD",
                    "captured": True,
                    "notes": {"run_id": "RFQ-1042", "quote_id": "QT-1042-V1"},
                }
            }
        },
    }

    with pytest.raises(ValueError, match="captured"):
        parse_captured_payment_event(failed)
    with pytest.raises(ValueError, match="INR"):
        parse_captured_payment_event(wrong_currency)
