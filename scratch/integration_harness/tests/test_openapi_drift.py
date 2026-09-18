"""Meaningful commercial request-field drift protection without a giant snapshot."""

import pytest
from app.main import app
from client.commercial_client import CommercialClient
from client.http_client import StockAwareClientError
from drift_checker import DriftChecker


def test_catalog_request_contract_requires_requested_unit():
    checker = DriftChecker()
    openapi = app.openapi()
    valid = {
        "business_id": "ff720599-56e8-53f4-9279-27ae059da37f",
        "run_id": "RFQ-DRIFT",
        "requested_text": "LED-9W",
        "requested_unit": "piece",
    }
    assert checker.validate_request(openapi, "/catalog/match", "post", valid) == []

    drifted = {**valid, "unit": valid["requested_unit"]}
    del drifted["requested_unit"]
    errors = checker.validate_request(openapi, "/catalog/match", "post", drifted)
    assert "Missing required field requested_unit for POST /catalog/match" in errors
    assert "Unknown field unit for POST /catalog/match" in errors


def test_commercial_mutation_request_fields_match_current_openapi():
    checker = DriftChecker()
    openapi = app.openapi()
    expected = {
        "/catalog/match": {"business_id", "run_id", "requested_text", "requested_unit"},
        "/inventory/check": {
            "business_id",
            "run_id",
            "product_id",
            "requested_qty",
            "requested_unit",
        },
        "/pricing/quote": {"business_id", "run_id", "buyer_id", "lines"},
        "/payments/create-link": {
            "business_id",
            "run_id",
            "quote_id",
            "quote_version",
            "amount_paise",
        },
        "/invoice/generate": {
            "business_id",
            "run_id",
            "quote_id",
            "quote_version",
            "payment_id",
        },
    }
    for path, fields in expected.items():
        assert checker.request_contract(openapi, path, "post")["fields"] == fields

    expected_response_fields = {
        "/catalog/match": {
            "status",
            "selected_product_id",
            "selected_sku",
            "candidates",
        },
        "/inventory/check": {"status", "product_id", "requested_qty", "available_qty"},
        "/pricing/quote": {
            "business_id",
            "run_id",
            "quote_id",
            "quote_version",
            "subtotal_paise",
            "tax_paise",
            "total_paise",
        },
        "/payments/create-link": {
            "payment_id",
            "quote_id",
            "quote_version",
            "status",
            "amount_paise",
            "currency",
        },
        "/invoice/generate": {
            "invoice_id",
            "invoice_number",
            "payment_id",
            "quote_id",
            "status",
        },
    }
    for path, fields in expected_response_fields.items():
        assert fields <= checker.response_fields(openapi, path, "post")


@pytest.mark.parametrize("status", [401, 403, 404, 422, 500, 503])
def test_http_client_never_treats_error_status_as_success(status):
    class Response:
        status_code = status
        text = "synthetic error"

        @staticmethod
        def json():
            return {"error": {"code": "SYNTHETIC", "message": "synthetic error"}}

    with pytest.raises(StockAwareClientError) as error:
        CommercialClient._handle_response(Response())
    assert error.value.status_code == status
