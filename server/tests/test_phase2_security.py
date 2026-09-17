from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api import business_context
from app.db.session import get_db
from app.main import app


def test_commercial_auth_fails_closed_and_errors_are_scoped(monkeypatch: pytest.MonkeyPatch):
    business_id = uuid4()
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as client:
            monkeypatch.setattr(
                business_context,
                "get_settings",
                lambda: SimpleNamespace(
                    internal_business_id="", internal_service_token=SecretStr("")
                ),
            )
            unavailable = client.get("/products")
            assert unavailable.status_code == 503
            assert unavailable.json()["error"]["code"] == "AUTHORIZATION_NOT_CONFIGURED"
            assert unavailable.json()["error"]["request_id"].startswith("req_")

            monkeypatch.setattr(
                business_context,
                "get_settings",
                lambda: SimpleNamespace(
                    internal_business_id=str(business_id),
                    internal_service_token=SecretStr("test-only-internal-token"),
                ),
            )
            unauthorized = client.get("/products")
            assert unauthorized.status_code == 401
            assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
            foreign = client.post(
                "/catalog/match",
                headers={"X-Internal-Service-Token": "test-only-internal-token"},
                json={
                    "business_id": str(uuid4()),
                    "run_id": "RFQ-test",
                    "requested_text": "LED-9W",
                    "requested_unit": "piece",
                },
            )
            assert foreign.status_code == 404
            assert foreign.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_phase2_openapi_has_only_frozen_routes():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "get" in schema["paths"]["/products"]
    assert "post" in schema["paths"]["/catalog/match"]
    assert "post" in schema["paths"]["/inventory/check"]
    assert "/pricing/quote" not in schema["paths"]
    assert "/payments/create-link" not in schema["paths"]
