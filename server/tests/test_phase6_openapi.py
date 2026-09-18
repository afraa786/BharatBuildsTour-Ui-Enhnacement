"""Frontend-facing response contract and commercial validation envelope."""

from fastapi.testclient import TestClient

from app.api.business_context import require_business_context
from app.main import app
from app.seed import DEMO_BUSINESS_ID


def test_openapi_commercial_schemas_are_safe_and_typed():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path, method in (
        ("/products", "get"),
        ("/catalog/match", "post"),
        ("/inventory/check", "post"),
        ("/pricing/quote", "post"),
        ("/payments/create-link", "post"),
        ("/payments/webhook", "post"),
        ("/payments/{payment_id}", "get"),
        ("/invoice/generate", "post"),
        ("/invoices/{invoice_id}", "get"),
        ("/invoices/{invoice_id}/artifact", "get"),
    ):
        assert method in paths[path]
    components = schema["components"]["schemas"]
    quote = components["QuoteOut"]["properties"]
    payment = components["PaymentOut"]["properties"]
    invoice = components["InvoiceOut"]["properties"]
    assert {"quote_id", "quote_version", "total_paise", "expires_at"} <= set(quote)
    assert {"payment_id", "status", "amount_paise", "provider_link_id"} <= set(payment)
    assert {"invoice_id", "invoice_number", "status", "download_url"} <= set(invoice)
    assert not {"cost_unit_paise", "min_margin_bps", "max_discount_bps"} & set(quote)
    assert not {"cost_unit_paise", "min_margin_bps", "max_discount_bps"} & set(payment)
    assert not {"cost_unit_paise", "min_margin_bps", "max_discount_bps"} & set(invoice)
    assert "X-Internal-Service-Token" not in str(paths["/payments/webhook"])


def test_commercial_validation_and_auth_errors_use_envelope():
    app.dependency_overrides[require_business_context] = lambda: DEMO_BUSINESS_ID
    try:
        with TestClient(app) as client:
            responses = [
                client.post("/payments/create-link", json={"business_id": "not-a-uuid"}),
                client.post("/invoice/generate", json={"business_id": "not-a-uuid"}),
                client.get("/payments/not-a-uuid"),
                client.get("/invoices/not-a-uuid"),
            ]
            for response in responses:
                assert response.status_code == 422
                assert response.json()["error"]["code"] == "VALIDATION_ERROR"
                assert response.json()["error"]["request_id"].startswith("req_")
            webhook = client.post("/payments/webhook", content=b"{}")
            assert webhook.status_code == 401
            assert webhook.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"
    finally:
        app.dependency_overrides.clear()
