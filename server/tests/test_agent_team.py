from app.modules.runs.agent_team import (
    AgentId,
    DeskId,
    delegate_to_agent,
    list_agents,
    list_desks,
    run_agentcraft_commerce_events,
    run_commerce_conversation,
    run_daily_summary_conversation,
)


def test_manager_led_team_has_expected_desks() -> None:
    desks = {desk["id"]: desk for desk in list_desks()}

    assert set(desks) == {
        DeskId.PRINCIPAL_MANAGER.value,
        DeskId.COMMERCE.value,
        DeskId.OPERATIONS.value,
        DeskId.OFFICE.value,
        DeskId.GROWTH.value,
        DeskId.AUDIT.value,
    }
    assert "Catalog/SKU Agent" in desks[DeskId.COMMERCE.value]["agents"]
    assert "Approval Guard Agent" in desks[DeskId.AUDIT.value]["agents"]


def test_mvp_agent_list_excludes_later_growth_and_delivery_agents() -> None:
    agents = {agent["id"]: agent for agent in list_agents(mvp_only=True)}

    assert AgentId.CUSTOMER_INTAKE.value in agents
    assert AgentId.REMINDER.value in agents
    assert AgentId.APPROVAL_GUARD.value in agents
    assert AgentId.INSTAGRAM_STORY.value not in agents
    assert AgentId.DELIVERY_DISPATCH.value not in agents


def test_commerce_agent_delegation_pipeline_is_deterministic() -> None:
    intake = delegate_to_agent(
        AgentId.CUSTOMER_INTAKE,
        {"text": "Need 20 LED bulbs and 10 MCBs tomorrow", "content_type": "text"},
    )
    assert intake["desk"] == "Commerce Desk"
    assert intake["result"]["normalized_text"] == "Need 20 LED bulbs and 10 MCBs tomorrow"

    matched = delegate_to_agent(AgentId.CATALOG_SKU, {"text": "20 led bulb 9w"})
    assert matched["result"]["line_items"][0]["sku"] == "LED-9W"

    stocked = delegate_to_agent(AgentId.INVENTORY, matched["result"])
    assert stocked["result"]["line_items"][0]["stock_status"] == "AVAILABLE"

    priced = delegate_to_agent(AgentId.PRICING, stocked["result"])
    assert priced["result"]["quote"]["total"] == "2242.00"

    quote = delegate_to_agent(AgentId.QUOTE, priced["result"])
    assert quote["result"]["quote_summary"]["approval_required"] is False


def test_payment_invoice_and_placeholder_agents_return_stable_shapes() -> None:
    payment = delegate_to_agent(AgentId.PAYMENT, {"run_id": "RFQ-1042"})
    assert payment["result"]["payment"]["payment_id"] == "pay_1042"

    invoice = delegate_to_agent(AgentId.INVOICE, {"run_id": "RFQ-1042"})
    assert invoice["result"]["invoice"]["artifact_key"] == "invoices/RFQ-1042/INV-1042.pdf"

    office = delegate_to_agent(AgentId.EMAIL, {"subject": "Supplier follow-up"})
    assert office["desk"] == "Office/PA Desk"
    assert office["result"]["status"] == "READY_NOT_CONNECTED"


def test_commerce_conversation_passes_outputs_between_agents() -> None:
    result = run_commerce_conversation("20 led bulb 9w")

    assert result["workflow"] == "commerce_quote"
    assert result["status"] == "READY_TO_SEND"
    assert [turn["to"] for turn in result["transcript"]] == [
        "Customer Intake Agent",
        "Catalog/SKU Agent",
        "Inventory Agent",
        "Pricing Agent",
        "Quote Agent",
        "Principal Manager",
    ]
    assert result["result"]["quote_summary"]["total"] == "2242.00"


def test_commerce_conversation_stops_for_catalog_clarification() -> None:
    result = run_commerce_conversation("20 mystery part")

    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["transcript"][-1]["to"] == "Principal Manager"
    assert result["result"]["unresolved_items"][0]["match_status"] == "NOT_FOUND"


def test_daily_summary_conversation_routes_blockers_to_approval_guard() -> None:
    result = run_daily_summary_conversation(
        {
            "open_quotes": [{"run_id": "RFQ-1"}],
            "pending_payments": [],
            "low_stock": [{"sku": "MCB-32A"}],
            "urgent_blockers": [{"run_id": "RFQ-2", "status": "APPROVAL_PENDING"}],
        }
    )

    assert result["status"] == "READY"
    assert [turn["to"] for turn in result["transcript"]] == [
        "Daily Summary Agent",
        "Approval Guard Agent",
        "Principal Manager",
    ]
    assert result["result"]["urgent_blockers_count"] == 1


def test_agentcraft_events_match_frontend_contract() -> None:
    events = run_agentcraft_commerce_events(run_id="RFQ-1042", text="20 led bulb 9w")

    assert events
    assert events[0].keys() == {
        "run_id",
        "from_agent",
        "to_agent",
        "type",
        "message",
        "status",
        "timestamp",
    }
    assert events[0]["run_id"] == "RFQ-1042"
    assert events[0]["from_agent"] == "manager"
    assert events[0]["to_agent"] == "sales"
    assert events[-1]["to_agent"] == "manager"
