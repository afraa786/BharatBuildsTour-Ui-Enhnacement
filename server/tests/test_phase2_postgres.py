"""Phase 2 endpoint checks against the disposable Phase 1 PostgreSQL database."""

from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.api.business_context import require_business_context
from app.db.session import get_db
from app.main import app
from app.modules.catalog.models import Product, ProductAlias, ProductSubstitute
from app.modules.catalog.normalization import normalize_catalog_text
from app.modules.identity.models import Business
from app.modules.inventory.models import Inventory, StockMovement
from app.seed import DEMO_BUSINESS_ID, seed_demo

pytest_plugins = ["test_phase1_postgres"]


@pytest.fixture
def api_client(pg_session: Session) -> Iterator[TestClient]:
    seed_demo(pg_session)

    def session_override() -> Iterator[Session]:
        yield pg_session

    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[require_business_context] = lambda: DEMO_BUSINESS_ID
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _product_id(session: Session, sku: str, business_id: UUID = DEMO_BUSINESS_ID) -> UUID:
    return session.scalar(
        select(Product.id).where(Product.business_id == business_id, Product.sku == sku)
    )


def _match(
    client: TestClient, text: str, unit: str = "piece", business_id: UUID = DEMO_BUSINESS_ID
):
    return client.post(
        "/catalog/match",
        json={
            "business_id": str(business_id),
            "run_id": "RFQ-p2-test",
            "requested_text": text,
            "requested_unit": unit,
        },
    )


def _check(
    client: TestClient,
    product_id: UUID,
    qty: str,
    *,
    unit: str | None = None,
    business_id: UUID = DEMO_BUSINESS_ID,
):
    body = {
        "business_id": str(business_id),
        "run_id": "RFQ-p2-test",
        "product_id": str(product_id),
        "requested_qty": qty,
    }
    if unit is not None:
        body["requested_unit"] = unit
    return client.post("/inventory/check", json=body)


def _new_product(
    session: Session,
    business_id: UUID,
    sku: str,
    name: str,
    *,
    active: bool = True,
    indivisible: bool = True,
    sellable_unit: str = "piece",
    stock_unit: str = "piece",
    pack_size: str = "1",
) -> UUID:
    product_id = uuid4()
    session.execute(
        insert(Product).values(
            id=product_id,
            business_id=business_id,
            sku=sku,
            normalized_sku=normalize_catalog_text(sku),
            name=name,
            normalized_name=normalize_catalog_text(name),
            sellable_unit=sellable_unit,
            stock_unit=stock_unit,
            pack_size=Decimal(pack_size),
            indivisible=indivisible,
            cost_unit_paise=100,
            base_unit_price_paise=200,
            gst_rate_bps=1800,
            active=active,
        )
    )
    return product_id


def test_catalog_exact_sources_and_normalization(
    api_client: TestClient, pg_session: Session
) -> None:
    expected_id = str(_product_id(pg_session, "LED-9W"))
    cases = [
        ("LED-9W", "sku"),
        ("  led-9w  ", "sku"),
        ("9W LED Bulb", "name"),
        ("  9W   LED\u00a0Bulb  ", "name"),
        ("9 watt led", "alias"),
    ]
    for text, match_type in cases:
        response = _match(api_client, text)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "MATCHED"
        assert body["selected_product_id"] == expected_id
        assert body["selected_sku"] == "LED-9W"
        assert body["candidates"][0]["match_type"] == match_type
        assert "cost_unit_paise" not in response.text


def test_catalog_ambiguity_never_selects(api_client: TestClient, pg_session: Session) -> None:
    response = _match(api_client, "32 amp mcb")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "AMBIGUOUS"
    assert body["selected_product_id"] is None
    assert body["selected_sku"] is None
    assert len(body["candidates"]) == 2
    assert {candidate["match_type"] for candidate in body["candidates"]} == {"alias"}

    second_id = _new_product(pg_session, DEMO_BUSINESS_ID, "LED-TEST", "9W LED Bulb Variant")
    pg_session.execute(
        insert(ProductAlias).values(
            id=uuid4(),
            business_id=DEMO_BUSINESS_ID,
            product_id=second_id,
            alias_text="9W LED Bulb",
            normalized_alias=normalize_catalog_text("9W LED Bulb"),
        )
    )
    collision = _match(api_client, "9W LED Bulb")
    assert collision.json()["status"] == "AMBIGUOUS"
    assert collision.json()["selected_product_id"] is None


def test_catalog_not_found_inactive_unit_and_no_fuzzy(api_client: TestClient, pg_session: Session):
    inactive = _new_product(pg_session, DEMO_BUSINESS_ID, "OLD-ITEM", "Old Switch", active=False)
    pg_session.execute(
        insert(ProductAlias).values(
            id=uuid4(),
            business_id=DEMO_BUSINESS_ID,
            product_id=inactive,
            alias_text="obsolete switch",
            normalized_alias=normalize_catalog_text("obsolete switch"),
        )
    )
    for text in ("Old Switch", "obsolete switch", "Copr Wre 2.5", "unknown", "LED-13W"):
        body = _match(api_client, text).json()
        assert body["status"] == "NOT_FOUND"
        assert body["selected_sku"] is None
        assert body["candidates"] == []

    mismatch = _match(api_client, "LED-9W", "box").json()
    assert mismatch["status"] == "AMBIGUOUS"
    assert mismatch["reason_code"] == "UNIT_MISMATCH"
    assert mismatch["selected_product_id"] is None
    assert len(mismatch["candidates"]) == 1


def test_catalog_business_isolation_and_safe_list(api_client: TestClient, pg_session: Session):
    other_business = uuid4()
    pg_session.execute(insert(Business).values(id=other_business, display_name="Other Business"))
    other_id = _new_product(pg_session, other_business, "OTHER-ONLY", "Other Only")
    pg_session.execute(
        insert(ProductAlias).values(
            id=uuid4(),
            business_id=other_business,
            product_id=other_id,
            alias_text="secret other alias",
            normalized_alias=normalize_catalog_text("secret other alias"),
        )
    )
    for text in ("OTHER-ONLY", "Other Only", "secret other alias"):
        assert _match(api_client, text).json()["status"] == "NOT_FOUND"
    for response in (
        _match(api_client, "LED-9W", business_id=other_business),
        _check(api_client, other_id, "1.000"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
        assert str(other_id) not in response.text

    listing = api_client.get("/products", params={"limit": 5, "offset": 1})
    assert listing.status_code == 200
    assert len(listing.json()) == 5
    assert "OTHER-ONLY" not in listing.text
    assert "cost_unit_paise" not in listing.text
    assert "min_margin_bps" not in listing.text
    assert "max_discount_bps" not in listing.text


def test_inventory_status_precedence_boundaries(api_client: TestClient, pg_session: Session):
    product_id = _product_id(pg_session, "LED-9W")
    cases = [
        ("1.000", "AVAILABLE"),
        ("25.000", "LOW_STOCK"),
        ("30.000", "LOW_STOCK"),
        ("31.000", "INSUFFICIENT_STOCK"),
    ]
    for qty, expected in cases:
        response = _check(api_client, product_id, qty)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == expected
        assert body["available_qty"] == "30.000"
        assert body["requested_qty"] == qty

    pg_session.execute(
        update(Inventory)
        .where(Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == product_id)
        .values(on_hand_qty=Decimal("0.000"))
    )
    assert _check(api_client, product_id, "1.000").json()["status"] == "OUT_OF_STOCK"


def test_inventory_threshold_null_fraction_and_indivisible(
    api_client: TestClient, pg_session: Session
):
    product_id = _new_product(
        pg_session,
        DEMO_BUSINESS_ID,
        "WIRE-FRAC",
        "Fractional Wire",
        indivisible=False,
        sellable_unit="meter",
        stock_unit="meter",
    )
    pg_session.execute(
        insert(Inventory).values(
            business_id=DEMO_BUSINESS_ID,
            product_id=product_id,
            on_hand_qty=Decimal("50.000"),
            reorder_threshold=None,
            version=1,
        )
    )
    assert _check(api_client, product_id, "1.500").json()["status"] == "AVAILABLE"
    assert _check(api_client, product_id, "50.000").json()["status"] == "AVAILABLE"
    pg_session.execute(
        update(Inventory)
        .where(Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == product_id)
        .values(reorder_threshold=Decimal("10.000"))
    )
    assert _check(api_client, product_id, "40.000").json()["status"] == "LOW_STOCK"
    assert _check(api_client, product_id, "39.999").json()["status"] == "AVAILABLE"
    indivisible_id = _product_id(pg_session, "LED-9W")
    response = _check(api_client, indivisible_id, "1.500")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_inventory_pack_conversion_is_explicit(api_client: TestClient, pg_session: Session):
    product_id = _product_id(pg_session, "SCREW-M4-25-P100")
    response = _check(api_client, product_id, "2.000", unit="pack")
    assert response.status_code == 200
    assert response.json()["requested_qty"] == "200.000"
    assert response.json()["stock_unit"] == "piece"
    invalid = _check(api_client, product_id, "2.000", unit="box")
    assert invalid.status_code == 422
    half_pack = _check(api_client, product_id, "0.500", unit="pack")
    assert half_pack.status_code == 422


def test_inventory_substitutes_rank_filter_and_read_only(
    api_client: TestClient, pg_session: Session
):
    source_id = _product_id(pg_session, "LED-9W")
    pg_session.execute(
        update(Inventory)
        .where(Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == source_id)
        .values(on_hand_qty=Decimal("2.000"))
    )
    initial_stock = pg_session.scalar(
        select(Inventory.on_hand_qty).where(
            Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == source_id
        )
    )
    initial_version = pg_session.scalar(
        select(Inventory.version).where(
            Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == source_id
        )
    )
    initial_movements = pg_session.scalar(select(func.count()).select_from(StockMovement))
    second_id = _new_product(pg_session, DEMO_BUSINESS_ID, "LED-ALT-2", "LED Alternative Two")
    inactive_id = _new_product(
        pg_session, DEMO_BUSINESS_ID, "LED-ALT-INACTIVE", "Inactive LED", active=False
    )
    for alternative_id, rank in ((second_id, 2), (inactive_id, 3)):
        pg_session.execute(
            insert(ProductSubstitute).values(
                id=uuid4(),
                business_id=DEMO_BUSINESS_ID,
                product_id=source_id,
                substitute_product_id=alternative_id,
                rank=rank,
            )
        )
        pg_session.execute(
            insert(Inventory).values(
                business_id=DEMO_BUSINESS_ID,
                product_id=alternative_id,
                on_hand_qty=Decimal("100.000"),
                reorder_threshold=None,
                version=1,
            )
        )
    response = _check(api_client, source_id, "5.000")
    assert response.status_code == 200
    assert response.json()["status"] == "INSUFFICIENT_STOCK"
    assert [item["rank"] for item in response.json()["substitutes"]] == [1, 2]
    assert _match(api_client, "LED-ALT-2").json()["selected_sku"] == "LED-ALT-2"
    assert _match(api_client, "LED Alternative Two").json()["status"] == "MATCHED"
    assert _match(api_client, "LED-ALT-INACTIVE").json()["status"] == "NOT_FOUND"
    assert (
        pg_session.scalar(
            select(Inventory.on_hand_qty).where(
                Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == source_id
            )
        )
        == initial_stock
    )
    assert (
        pg_session.scalar(
            select(Inventory.version).where(
                Inventory.business_id == DEMO_BUSINESS_ID, Inventory.product_id == source_id
            )
        )
        == initial_version
    )
    assert pg_session.scalar(select(func.count()).select_from(StockMovement)) == initial_movements


def test_inventory_validation_missing_and_cross_business(
    api_client: TestClient, pg_session: Session
):
    product_id = _product_id(pg_session, "LED-9W")
    for qty in ("0.000", "-1.000", "1.1234"):
        response = _check(api_client, product_id, qty)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert response.headers["content-type"] == "application/json"
    other_business = uuid4()
    pg_session.execute(insert(Business).values(id=other_business, display_name="Other Business"))
    other_id = _new_product(pg_session, other_business, "OTHER-STOCK", "Other Stock")
    pg_session.execute(
        insert(Inventory).values(
            business_id=other_business,
            product_id=other_id,
            on_hand_qty=Decimal("50.000"),
            version=1,
        )
    )
    not_found = _check(api_client, other_id, "1.000")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "NOT_FOUND"
    missing_id = _new_product(pg_session, DEMO_BUSINESS_ID, "MISSING-ROW", "Missing Inventory")
    missing = _check(api_client, missing_id, "1.000")
    assert missing.status_code == 500
    assert missing.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "SQL" not in missing.text
