"""Owner JWT and business isolation against the disposable PostgreSQL fixture."""

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.modules.catalog.models import Product
from app.modules.identity.models import Business, Buyer
from app.modules.identity.owner_models import User
from app.modules.runs.models import Run
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]


def _client(session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def _token(client: TestClient, phone: str) -> str:
    response = client.post("/auth/login", json={"phone_number": phone})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_owner_login_and_unknown_phone(pg_session: Session) -> None:
    try:
        with _client(pg_session) as client:
            assert (
                client.post("/auth/login", json={"phone_number": "8766700429"}).status_code == 200
            )
            assert (
                client.post("/auth/login", json={"phone_number": "0000000000"}).status_code == 401
            )
            token = _token(client, "8766700429")
            me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200
            assert me.json()["business_id"] == str(DEMO_BUSINESS_ID)
    finally:
        app.dependency_overrides.clear()


def test_owner_endpoints_require_token(pg_session: Session) -> None:
    paths = (
        "/me",
        "/dashboard/summary",
        "/categories",
        "/buyers",
        "/runs",
        "/invoices",
        "/reports/sales?from=2026-09-01T00:00:00Z&to=2026-10-01T00:00:00Z",
    )
    try:
        with _client(pg_session) as client:
            for path in paths:
                assert client.get(path).status_code == 401, path
            assert client.post("/categories", json={"name": "No Token"}).status_code == 401
            assert client.post("/buyers", json={"display_name": "No Token"}).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_owner_summary_matches_seed(pg_session: Session) -> None:
    try:
        with _client(pg_session) as client:
            token = _token(client, "8766700429")
            result = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
            assert result.status_code == 200
            summary = result.json()
            assert summary["total_sales_paise"] == 72000
            assert summary["runs_count_by_status"] == {
                "pending": 1,
                "shipped": 1,
                "paid": 1,
                "cancelled": 1,
            }
            assert summary["leads_count"] == 2
            assert summary["customers_count"] == 3
            assert len(summary["upcoming_deliveries"]) == 3
    finally:
        app.dependency_overrides.clear()


def test_owner_cross_business_reads_and_writes_are_isolated(pg_session: Session) -> None:
    business_id = uuid4()
    pg_session.add(Business(id=business_id, display_name="Second Owner Test"))
    pg_session.flush()
    pg_session.add(User(business_id=business_id, phone_number="8777700429", name="Second Owner"))
    product = Product(
        business_id=business_id,
        sku="SECOND-ONLY",
        normalized_sku="second only",
        name="Second Business Product",
        normalized_name="second business product",
        sellable_unit="piece",
        stock_unit="piece",
        pack_size=Decimal(1),
        cost_unit_paise=100,
        base_unit_price_paise=200,
        gst_rate_bps=0,
    )
    buyer = Buyer(business_id=business_id, display_name="Second Buyer", type="lead")
    run = Run(
        run_id=f"SECOND-{uuid4().hex}",
        business_id=business_id,
        status="pending",
        buyer_wa_id="+919810000099",
        buyer_name="Second Buyer",
        line_items=[],
    )
    pg_session.add_all((product, buyer, run))
    pg_session.flush()
    owner_product = pg_session.scalar(
        select(Product).where(Product.business_id == DEMO_BUSINESS_ID)
    )
    owner_buyer = pg_session.scalar(select(Buyer).where(Buyer.business_id == DEMO_BUSINESS_ID))
    try:
        with _client(pg_session) as client:
            owner = {"Authorization": f"Bearer {_token(client, '8766700429')}"}
            second = {"Authorization": f"Bearer {_token(client, '8777700429')}"}
            assert all(
                item["sku"] != "SECOND-ONLY"
                for item in client.get("/products", headers=owner).json()
            )
            assert all(
                item["sku"] == "SECOND-ONLY"
                for item in client.get("/products", headers=second).json()
            )
            assert len(client.get("/buyers", headers=second).json()) == 1
            assert len(client.get("/runs", headers=second).json()) == 1
            assert client.get("/invoices", headers=second).json() == []
            assert client.get(f"/runs/{run.run_id}", headers=owner).status_code == 404
            assert (
                client.patch(
                    f"/products/{owner_product.id}", headers=second, json={"name": "Stolen"}
                ).status_code
                == 404
            )
            assert (
                client.patch(
                    f"/buyers/{owner_buyer.id}", headers=second, json={"type": "customer"}
                ).status_code
                == 404
            )
            assert (
                client.patch(
                    "/runs/DEMO-OWNER-1001/status", headers=second, json={"status": "paid"}
                ).status_code
                == 404
            )
    finally:
        app.dependency_overrides.clear()
