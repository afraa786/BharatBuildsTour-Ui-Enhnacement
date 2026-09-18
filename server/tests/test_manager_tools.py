from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.runs import manager_tools
from app.modules.runs.state_machine import RunStatus


@dataclass
class FakeRun:
    run_id: str
    status: str
    buyer_wa_id: str = "buyer-1"
    buyer_name: str | None = "Acme Build"
    quote_snapshot: dict | None = None
    line_items: list | None = None
    quote_id: str | None = "Q-1042-V1"
    payment_id: str | None = None
    invoice_id: str | None = None
    updated_at: datetime | None = datetime(2026, 9, 18, tzinfo=UTC)
    created_at: datetime = datetime(2026, 9, 18, tzinfo=UTC)


@dataclass
class FakeEvent:
    role: str
    event: str
    event_metadata: dict | None
    created_at: datetime


def _tools_by_name():
    return {tool.name: tool for tool in manager_tools.build_tools(db=object())}


def test_manager_tool_catalog_contains_only_expected_read_tools() -> None:
    assert set(_tools_by_name()) == {
        "get_run_status",
        "why_run_blocked",
        "get_quote_details",
        "get_payment_status",
        "get_invoice_status",
        "get_inventory",
        "get_low_stock_items",
        "get_pending_payments",
        "get_open_quotes_today",
        "get_recent_customer_activity",
        "get_vendor_updates",
        "get_daily_summary",
        "get_run_timeline",
        "get_orders_in_progress",
        "get_reminders_due",
        "search_customer",
        "get_business_team",
        "get_mvp_team",
    }


def test_run_scoped_manager_tools_return_real_run_fields(monkeypatch) -> None:
    run = FakeRun(
        run_id="RFQ-1042",
        status=RunStatus.PAYMENT_PENDING.value,
        quote_snapshot={"total": "1180.00", "reason_codes": ["LOW_MARGIN"]},
        line_items=[{"requested_text": "wire", "match_status": "MATCHED"}],
        payment_id="pay_1042",
    )
    monkeypatch.setattr(manager_tools, "get_run_by_run_id", lambda db, run_id: run)
    tools = _tools_by_name()

    assert tools["get_run_status"].invoke({"run_id": "rfq-1042"}) == {
        "found": True,
        "run_id": "RFQ-1042",
        "status": RunStatus.PAYMENT_PENDING.value,
        "buyer_wa_id": "buyer-1",
        "total": "1180.00",
    }
    assert tools["get_quote_details"].invoke({"run_id": "RFQ-1042"})["quote_snapshot"] == {
        "total": "1180.00",
        "reason_codes": ["LOW_MARGIN"],
    }
    assert tools["get_payment_status"].invoke({"run_id": "RFQ-1042"}) == {
        "found": True,
        "run_id": "RFQ-1042",
        "payment_id": "pay_1042",
        "status": RunStatus.PAYMENT_PENDING.value,
        "amount": "1180.00",
    }


def test_invoice_and_blocked_tools_cover_generated_and_blocked(monkeypatch) -> None:
    blocked = FakeRun(
        run_id="RFQ-1043",
        status=RunStatus.WAITING_FOR_CLARIFICATION.value,
        line_items=[
            {"requested_text": "unknown cable", "match_status": "NO_MATCH"},
            {"requested_text": "bulb", "match_status": "MATCHED"},
        ],
    )
    invoiced = FakeRun(
        run_id="RFQ-1044",
        status=RunStatus.INVOICE_GENERATED.value,
        invoice_id="INV-1044",
    )

    def fake_get_run(db, run_id):
        return invoiced if run_id == "RFQ-1044" else blocked

    monkeypatch.setattr(manager_tools, "get_run_by_run_id", fake_get_run)
    tools = _tools_by_name()

    assert tools["why_run_blocked"].invoke({"run_id": "RFQ-1043"})[
        "unresolved_items"
    ] == ["unknown cable"]
    assert tools["get_invoice_status"].invoke({"run_id": "RFQ-1044"}) == {
        "found": True,
        "run_id": "RFQ-1044",
        "invoice_id": "INV-1044",
        "generated": True,
        "send_status": "sent",
        "status": RunStatus.INVOICE_GENERATED.value,
    }


def test_inventory_low_stock_vendor_and_reminder_tools() -> None:
    tools = _tools_by_name()

    assert tools["get_inventory"].invoke({})["desk"] == "Stock Desk"
    assert tools["get_low_stock_items"].invoke({})["items"]
    assert tools["get_vendor_updates"].invoke({})["items"] == []
    assert tools["get_reminders_due"].invoke({})["items"] == []
    assert tools["get_business_team"].invoke({})["owner_entrypoint"] == "Principal Manager"
    assert tools["get_mvp_team"].invoke({})["model"] == "manager_led_business_team"


def test_list_based_manager_tools(monkeypatch) -> None:
    runs = [
        FakeRun(
            run_id="RFQ-1",
            status=RunStatus.QUOTE_SENT.value,
            buyer_wa_id="buyer-1",
            quote_snapshot={"total": "100.00"},
        ),
        FakeRun(
            run_id="RFQ-2",
            status=RunStatus.PAYMENT_PENDING.value,
            buyer_wa_id="buyer-2",
            buyer_name="Beta Traders",
            quote_snapshot={"total": "200.00"},
        ),
        FakeRun(
            run_id="RFQ-3",
            status=RunStatus.APPROVAL_PENDING.value,
            buyer_wa_id="buyer-3",
            quote_snapshot={"total": "300.00"},
        ),
    ]
    monkeypatch.setattr(
        manager_tools,
        "list_runs",
        lambda db, status=None: [run for run in runs if status is None or run.status == status],
    )
    tools = _tools_by_name()

    assert tools["get_pending_payments"].invoke({})["items"][0]["run_id"] == "RFQ-2"
    assert tools["get_open_quotes_today"].invoke({})["items"][0]["run_id"] == "RFQ-1"
    assert tools["get_daily_summary"].invoke({})["urgent_blockers"][0]["run_id"] == "RFQ-3"
    assert tools["get_orders_in_progress"].invoke({})["items"][0]["run_id"] == "RFQ-2"
    assert tools["get_recent_customer_activity"].invoke({"query": "beta"})["items"][0][
        "run_id"
    ] == "RFQ-2"
    assert tools["search_customer"].invoke({"query": "buyer-1"})["items"][0]["run_id"] == "RFQ-1"


def test_run_timeline_tool(monkeypatch) -> None:
    run = FakeRun(run_id="RFQ-1042", status=RunStatus.QUOTE_SENT.value)
    event = FakeEvent(
        role="Sales Desk",
        event="Quote sent",
        event_metadata={"channel": "whatsapp"},
        created_at=datetime(2026, 9, 18, tzinfo=UTC),
    )
    monkeypatch.setattr(manager_tools, "get_run_by_run_id", lambda db, run_id: run)
    monkeypatch.setattr(manager_tools, "get_timeline", lambda db, found_run: [event])

    result = _tools_by_name()["get_run_timeline"].invoke({"run_id": "RFQ-1042"})

    assert result["items"] == [
        {
            "role": "Sales Desk",
            "event": "Quote sent",
            "metadata": {"channel": "whatsapp"},
            "created_at": "2026-09-18T00:00:00+00:00",
        }
    ]
