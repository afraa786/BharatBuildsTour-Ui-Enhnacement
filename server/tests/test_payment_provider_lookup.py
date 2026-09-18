"""Razorpay reference lookup uses documented HTTP API; network is fully mocked."""

from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.api.commercial import CommercialError
from app.modules.payments import provider as module


def _mock_client(monkeypatch: pytest.MonkeyPatch, handler):
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        module.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            razorpay_key_id="rzp_test_synthetic",
            razorpay_key_secret=SecretStr("synthetic-only-secret"),
        ),
    )


def _link_payload(reference_id: str) -> dict:
    return {
        "id": "plink_synthetic",
        "short_url": "https://rzp.io/i/synthetic",
        "reference_id": reference_id,
        "amount": 10000,
        "currency": "INR",
        "status": "created",
    }


def test_reference_lookup_uses_documented_get_and_parses_link(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/payment_links/"
        assert request.url.params["reference_id"] == "intent-123"
        return httpx.Response(200, json=_link_payload("intent-123"))

    _mock_client(monkeypatch, handler)
    link = module.RazorpayProvider().find_link(reference_id="intent-123")
    assert link is not None
    assert link.reference_id == "intent-123"
    assert link.amount_paise == 10000


def test_reference_lookup_empty_collection_is_not_a_new_create(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"payment_links": []})

    _mock_client(monkeypatch, handler)
    assert module.RazorpayProvider().find_link(reference_id="intent-123") is None


@pytest.mark.parametrize("payload", [{"unexpected": True}, {"payment_links": [{}, {}]}])
def test_reference_lookup_rejects_malformed_or_ambiguous_response(monkeypatch, payload):
    _mock_client(monkeypatch, lambda request: httpx.Response(200, json=payload))
    with pytest.raises(CommercialError) as error:
        module.RazorpayProvider().find_link(reference_id="intent-123")
    assert error.value.code == "PROVIDER_OUTCOME_UNKNOWN"


def test_reference_lookup_timeout_fails_closed(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    _mock_client(monkeypatch, handler)
    with pytest.raises(CommercialError) as error:
        module.RazorpayProvider().find_link(reference_id="intent-123")
    assert error.value.code == "PROVIDER_OUTCOME_UNKNOWN"
