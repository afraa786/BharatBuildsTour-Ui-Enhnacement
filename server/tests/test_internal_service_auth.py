"""Internal service token and single-business binding; credentials are synthetic."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api import business_context
from app.db.session import get_db
from app.main import app
from app.modules.catalog.models import Product
from app.modules.identity.models import Business
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]

TOKEN = "synthetic-internal-service-token-for-tests"


def _configure(monkeypatch: pytest.MonkeyPatch, business_id: str, token: str) -> None:
    monkeypatch.setattr(
        business_context,
        "get_settings",
        lambda: SimpleNamespace(
            internal_business_id=business_id,
            internal_service_token=SecretStr(token),
        ),
    )


def test_missing_configuration_missing_token_and_wrong_token(monkeypatch: pytest.MonkeyPatch):
    with TestClient(app) as client:
        _configure(monkeypatch, "", "")
        unconfigured = client.get("/products", headers={"X-Internal-Service-Token": TOKEN})
        assert unconfigured.status_code == 503
        assert unconfigured.json()["error"]["code"] == "AUTHORIZATION_NOT_CONFIGURED"

        _configure(monkeypatch, str(DEMO_BUSINESS_ID), TOKEN)
        for headers in ({}, {"X-Internal-Service-Token": "incorrect"}):
            denied = client.get("/products", headers=headers)
            assert denied.status_code == 401
            assert denied.json()["error"]["code"] == "UNAUTHORIZED"
            assert TOKEN not in denied.text

        _configure(monkeypatch, "not-a-uuid", TOKEN)
        malformed = client.get("/products", headers={"X-Internal-Service-Token": TOKEN})
        assert malformed.status_code == 503
        assert TOKEN not in malformed.text


def test_constant_time_comparison_and_business_claim(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch, str(DEMO_BUSINESS_ID), TOKEN)
    compared = []
    original = business_context.hmac.compare_digest

    def spy(actual: str, expected: str) -> bool:
        compared.append((actual, expected))
        return original(actual, expected)

    monkeypatch.setattr(business_context.hmac, "compare_digest", spy)
    with TestClient(app) as client:
        foreign = client.post(
            "/catalog/match",
            headers={"X-Internal-Service-Token": TOKEN},
            json={
                "business_id": str(uuid4()),
                "run_id": "RFQ-auth-test",
                "requested_text": "LED-9W",
                "requested_unit": "piece",
            },
        )
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "NOT_FOUND"
    assert TOKEN not in foreign.text
    assert compared == [(TOKEN, TOKEN)]


def test_authenticated_product_read_is_business_scoped(
    pg_session: Session, monkeypatch: pytest.MonkeyPatch
):
    foreign_business = uuid4()
    pg_session.add(Business(id=foreign_business, display_name="Foreign Test Business"))
    pg_session.flush()
    pg_session.add(
        Product(
            business_id=foreign_business,
            sku="FOREIGN-ONLY",
            normalized_sku="foreign-only",
            name="Foreign Only Product",
            normalized_name="foreign only product",
            sellable_unit="piece",
            stock_unit="piece",
            pack_size=Decimal("1"),
            cost_unit_paise=100,
            base_unit_price_paise=200,
            gst_rate_bps=0,
        )
    )
    pg_session.flush()
    _configure(monkeypatch, str(DEMO_BUSINESS_ID), TOKEN)
    app.dependency_overrides[get_db] = lambda: pg_session
    try:
        with TestClient(app) as client:
            products = client.get("/products", headers={"X-Internal-Service-Token": TOKEN})
            assert products.status_code == 200
            assert products.json()
            assert all(item["sku"] != "FOREIGN-ONLY" for item in products.json())
            assert TOKEN not in products.text
    finally:
        app.dependency_overrides.clear()


def test_production_omits_in_memory_demo_routes(monkeypatch: pytest.MonkeyPatch):
    from app import main

    settings = SimpleNamespace(environment="production", cors_origins=[])
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    production_app = main.create_app()
    paths = production_app.openapi()["paths"]
    assert "/demo/webhook/whatsapp" not in paths
    assert "/demo/payments/{payment_id}/confirm" not in paths
    assert "/payments/create-link" in paths
