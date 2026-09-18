import json

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import app
from app.modules.payments import router as payments_router


class _Settings:
    razorpay_webhook_secret = SecretStr("webhook-test-secret")


def _signature(body: bytes, secret: str) -> str:
    import hmac
    from hashlib import sha256

    return hmac.new(secret.encode(), body, sha256).hexdigest()


def test_razorpay_webhook_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setattr(payments_router, "get_settings", lambda: _Settings())
    body = json.dumps({"event": "payment.captured"}).encode()

    with TestClient(app) as client:
        response = client.post(
            "/payments/razorpay/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "0" * 64},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid razorpay signature"


def test_razorpay_webhook_accepts_captured_payment_without_marking_paid(monkeypatch) -> None:
    monkeypatch.setattr(payments_router, "get_settings", lambda: _Settings())
    payload = {
        "id": "evt_test_123",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "order_id": "order_test_123",
                    "amount": 141600,
                    "currency": "INR",
                    "captured": True,
                    "notes": {"run_id": "RFQ-1042", "quote_id": "QT-1042-V1"},
                    "created_at": 1797595200,
                }
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()

    with TestClient(app) as client:
        response = client.post(
            "/payments/razorpay/webhook",
            content=body,
            headers={"X-Razorpay-Signature": _signature(body, "webhook-test-secret")},
        )

    assert response.status_code == 202
    assert response.json() == {
        "accepted": True,
        "provider_event_id": "evt_test_123",
        "provider_payment_id": "pay_test_123",
        "run_id": "RFQ-1042",
        "quote_id": "QT-1042-V1",
        "next_action": "persist_payment_event_and_generate_invoice",
    }
