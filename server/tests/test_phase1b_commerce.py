from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.modules.catalog.service import search_products
from app.modules.commerce.service import process_customer_commerce_message
from app.modules.commerce.tools import build_commerce_tools
from app.modules.identity.models import Business, Buyer
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]


def test_commerce_tools_catalog_search(pg_session: Session):
    tools = build_commerce_tools(pg_session, DEMO_BUSINESS_ID)
    search_tool = next(t for t in tools if t.name == "search_products")

    # Test fuzzy search on Name
    results = search_tool.invoke({"query": "wire"})
    assert isinstance(results, list)
    assert len(results) > 0
    assert any("wire" in r["name"].lower() for r in results)

    # Test fuzzy search on Alias (if any in seed data)
    # The seed data might have some aliases. We just verify the tool runs successfully.
    results = search_tool.invoke({"query": "cable"})
    assert isinstance(results, list)


def test_commerce_tools_inventory_check(pg_session: Session):
    tools = build_commerce_tools(pg_session, DEMO_BUSINESS_ID)
    search_tool = next(t for t in tools if t.name == "search_products")
    check_inventory_tool = next(t for t in tools if t.name == "check_inventory")

    # Find a product
    results = search_tool.invoke({"query": "wire"})
    assert len(results) > 0
    product_id = results[0]["id"]

    # Check its inventory
    inv_result = check_inventory_tool.invoke({"product_id": product_id, "requested_qty": 2})
    assert "status" in inv_result
    assert inv_result["status"] in ["AVAILABLE", "OUT_OF_STOCK", "INSUFFICIENT_STOCK", "LOW_STOCK"]


def test_acceptance_harness_commerce_flow(pg_session: Session):
    # This serves as the acceptance harness
    wa_id = "911234567890"
    phone_id = "test_phone_id"

    # 1. First interaction: "LED chahiye"
    responses = process_customer_commerce_message(
        pg_session, DEMO_BUSINESS_ID, phone_id, wa_id, "LED chahiye"
    )
    assert len(responses) == 1

    # Verify Lead was created
    buyer = (
        pg_session.query(Buyer).filter_by(whatsapp_e164=wa_id, business_id=DEMO_BUSINESS_ID).first()
    )
    assert buyer is not None
    assert buyer.is_customer is False

    # Note: process_customer_commerce_message invokes LLM.
    # If API keys are not set, it falls back to a fixed message.
    # To fully test without API keys, we just verify the identity state.

    # 2. "payment hogaya"
    responses = process_customer_commerce_message(
        pg_session, DEMO_BUSINESS_ID, phone_id, wa_id, "payment hogaya"
    )
    assert len(responses) == 1

    pg_session.refresh(buyer)
    assert buyer.is_customer is False  # Must not promote Buyer!


def test_catalog_search_is_literal_bounded_deduplicated_and_tenant_scoped(
    pg_session: Session,
):
    literal_percent = search_products(pg_session, DEMO_BUSINESS_ID, "%")
    literal_underscore = search_products(pg_session, DEMO_BUSINESS_ID, "_")
    results = search_products(pg_session, DEMO_BUSINESS_ID, "LED")
    other_business_id = uuid4()
    pg_session.execute(
        insert(Business).values(id=other_business_id, display_name="Catalog isolation fixture")
    )
    pg_session.flush()

    assert literal_percent == []
    assert literal_underscore == []
    assert len(results) <= 20
    assert len({item.product_id for item in results}) == len(results)
    assert search_products(pg_session, other_business_id, "LED") == []


def test_inventory_tool_rejects_cross_tenant_product(pg_session: Session):
    product = search_products(pg_session, DEMO_BUSINESS_ID, "LED")[0]
    other_business_id = uuid4()
    pg_session.execute(
        insert(Business).values(id=other_business_id, display_name="Inventory isolation fixture")
    )
    pg_session.flush()
    other_tools = build_commerce_tools(pg_session, other_business_id)
    inventory_tool = next(tool for tool in other_tools if tool.name == "check_inventory")

    result = inventory_tool.invoke({"product_id": str(product.product_id), "requested_qty": 1})
    assert "error" in result
    assert "Product not found" in result["error"]
