from app.modules.runs.agent_team import AgentId, DeskId, delegate_to_agent, list_agents, list_desks


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
