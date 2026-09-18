"""Real, read-only tools the Manager agent can call.

Every tool here only reads and returns actual data -- run status, stock,
payments, quotes -- computed the same deterministic way the rest of the
app does. The LLM decides *when* to call a tool based on what the admin
asked; it never gets to decide *what* the data says. There is
deliberately no approve/reject tool: those two mutating actions stay
gated behind the admin typing the exact command themselves
(process_admin_message's regex match, tried before the agent ever runs).
"""

from datetime import UTC, datetime

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.runs import mock_desks
from app.modules.runs.agent_team import (
    list_agents,
    list_desks,
    run_commerce_conversation,
    run_daily_summary_conversation,
)
from app.modules.runs.repository import get_run_by_run_id, get_timeline, list_runs
from app.modules.runs.state_machine import RunStatus


class RunIdInput(BaseModel):
    run_id: str = Field(description="The exact RFQ run ID, e.g. RFQ-1042")


class CustomerSearchInput(BaseModel):
    query: str = Field(description="Buyer phone number, name, or business search text")


class TextInput(BaseModel):
    text: str = Field(description="The source text to route through the agent conversation")


def _get_run_status(db: Session, run_id: str) -> dict:
    run = get_run_by_run_id(db, run_id.strip().upper())
    if run is None:
        return {"found": False}
    return {
        "found": True,
        "run_id": run.run_id,
        "status": run.status,
        "buyer_wa_id": run.buyer_wa_id,
        "total": run.quote_snapshot["total"] if run.quote_snapshot else None,
    }


def _get_quote_details(db: Session, run_id: str) -> dict:
    run = get_run_by_run_id(db, run_id.strip().upper())
    if run is None:
        return {"found": False}
    return {
        "found": True,
        "run_id": run.run_id,
        "status": run.status,
        "quote_id": run.quote_id,
        "buyer_wa_id": run.buyer_wa_id,
        "line_items": run.line_items,
        "quote_snapshot": run.quote_snapshot,
    }


def _get_payment_status(db: Session, run_id: str) -> dict:
    run = get_run_by_run_id(db, run_id.strip().upper())
    if run is None:
        return {"found": False}
    payment_statuses = {
        RunStatus.PAYMENT_LINK_SENT.value,
        RunStatus.PAYMENT_PENDING.value,
        RunStatus.PAYMENT_FAILED.value,
        RunStatus.PAYMENT_EXPIRED.value,
        RunStatus.PAYMENT_CONFIRMED.value,
        RunStatus.INVOICE_GENERATED.value,
        RunStatus.ORDER_CONFIRMED.value,
    }
    return {
        "found": True,
        "run_id": run.run_id,
        "payment_id": run.payment_id,
        "status": run.status if run.status in payment_statuses else "NOT_STARTED",
        "amount": run.quote_snapshot["total"] if run.quote_snapshot else None,
    }


def _get_invoice_status(db: Session, run_id: str) -> dict:
    run = get_run_by_run_id(db, run_id.strip().upper())
    if run is None:
        return {"found": False}
    generated = run.status in {
        RunStatus.INVOICE_GENERATED.value,
        RunStatus.ORDER_CONFIRMED.value,
    }
    return {
        "found": True,
        "run_id": run.run_id,
        "invoice_id": run.invoice_id,
        "generated": generated,
        "send_status": "sent" if generated else "not_sent",
        "status": run.status,
    }


def _why_run_blocked(db: Session, run_id: str) -> dict:
    run = get_run_by_run_id(db, run_id.strip().upper())
    if run is None:
        return {"found": False}
    if run.status == RunStatus.WAITING_FOR_CLARIFICATION.value:
        unresolved = [
            item["requested_text"]
            for item in run.line_items
            if item.get("match_status") != "MATCHED"
        ]
        return {
            "found": True,
            "status": run.status,
            "reason": "waiting on buyer clarification",
            "unresolved_items": unresolved,
        }
    if run.status == RunStatus.APPROVAL_PENDING.value:
        reason_codes = run.quote_snapshot.get("reason_codes", []) if run.quote_snapshot else []
        return {
            "found": True,
            "status": run.status,
            "reason": "waiting on owner approval",
            "reason_codes": reason_codes,
        }
    return {"found": True, "status": run.status, "reason": "not blocked"}


def _get_recent_customer_activity(db: Session, query: str) -> dict:
    normalized = query.strip().casefold()
    runs = [
        run
        for run in list_runs(db)
        if normalized in run.buyer_wa_id.casefold()
        or (run.buyer_name and normalized in run.buyer_name.casefold())
    ][:10]
    return {
        "query": query,
        "items": [
            {
                "run_id": run.run_id,
                "buyer_wa_id": run.buyer_wa_id,
                "buyer_name": run.buyer_name,
                "status": run.status,
                "total": run.quote_snapshot["total"] if run.quote_snapshot else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            }
            for run in runs
        ],
    }


def _get_vendor_updates(db: Session) -> dict:
    return {
        "desk": "Procurement Desk",
        "items": [],
        "note": "No vendor update store is connected yet.",
    }


def _get_daily_summary(db: Session) -> dict:
    return {
        "open_quotes": _get_open_quotes_today(db)["items"],
        "low_stock": _get_low_stock_items(db)["items"],
        "pending_payments": _get_pending_payments(db)["items"],
        "urgent_blockers": [
            {
                "run_id": run.run_id,
                "status": run.status,
                "buyer_wa_id": run.buyer_wa_id,
            }
            for run in list_runs(db)
            if run.status
            in {
                RunStatus.WAITING_FOR_CLARIFICATION.value,
                RunStatus.APPROVAL_PENDING.value,
            }
        ],
    }


def _get_run_timeline(db: Session, run_id: str) -> dict:
    run = get_run_by_run_id(db, run_id.strip().upper())
    if run is None:
        return {"found": False}
    return {
        "found": True,
        "run_id": run.run_id,
        "items": [
            {
                "role": event.role,
                "event": event.event,
                "metadata": event.event_metadata,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in get_timeline(db, run)
        ],
    }


def _get_orders_in_progress(db: Session) -> dict:
    statuses = {
        RunStatus.ACCEPTED.value,
        RunStatus.PAYMENT_LINK_SENT.value,
        RunStatus.PAYMENT_PENDING.value,
        RunStatus.PAYMENT_CONFIRMED.value,
        RunStatus.INVOICE_GENERATED.value,
    }
    return {
        "items": [
            {
                "run_id": run.run_id,
                "status": run.status,
                "buyer_wa_id": run.buyer_wa_id,
                "total": run.quote_snapshot["total"] if run.quote_snapshot else None,
            }
            for run in list_runs(db)
            if run.status in statuses
        ]
    }


def _get_reminders_due(db: Session) -> dict:
    return {
        "items": [],
        "note": "No reminder store is connected yet.",
    }


def _search_customer(db: Session, query: str) -> dict:
    return _get_recent_customer_activity(db, query)


def _get_business_team() -> dict:
    return {
        "model": "manager_led_business_team",
        "owner_entrypoint": "Principal Manager",
        "desks": list_desks(),
        "agents": list_agents(),
    }


def _get_mvp_team() -> dict:
    return {
        "model": "manager_led_business_team",
        "owner_entrypoint": "Principal Manager",
        "desks": list_desks(mvp_only=True),
        "agents": list_agents(mvp_only=True),
    }


def _preview_commerce_conversation(text: str) -> dict:
    return run_commerce_conversation(text)


def _preview_daily_summary_conversation(db: Session) -> dict:
    return run_daily_summary_conversation(_get_daily_summary(db))


def _get_inventory(db: Session) -> dict:
    items = [
        {
            "sku": product["sku"],
            "name": product["name"],
            "unit": product["unit"],
            "unit_price": str(product["unit_price"]),
            "stock_qty": product["stock_qty"],
            "reorder_threshold": product["reorder_threshold"],
        }
        for product in mock_desks.CATALOG
    ]
    return {"desk": "Stock Desk", "items": items}


def _get_low_stock_items(db: Session) -> dict:
    items = [
        {
            "sku": product["sku"],
            "name": product["name"],
            "stock_qty": product["stock_qty"],
            "reorder_threshold": product["reorder_threshold"],
        }
        for product in mock_desks.CATALOG
        if product["stock_qty"] <= product["reorder_threshold"]
    ]
    return {"desk": "Stock Desk", "items": items}


def _get_pending_payments(db: Session) -> dict:
    pending_statuses = {RunStatus.PAYMENT_LINK_SENT.value, RunStatus.PAYMENT_PENDING.value}
    runs = [run for run in list_runs(db) if run.status in pending_statuses]
    return {
        "desk": "Accounts Desk",
        "items": [
            {
                "run_id": run.run_id,
                "buyer_wa_id": run.buyer_wa_id,
                "total": run.quote_snapshot["total"] if run.quote_snapshot else None,
            }
            for run in runs
        ],
    }


def _get_open_quotes_today(db: Session) -> dict:
    today = datetime.now(UTC).date()
    runs = [
        run
        for run in list_runs(db, status=RunStatus.QUOTE_SENT.value)
        if run.created_at.date() == today
    ]
    return {
        "desk": "Sales Desk",
        "items": [
            {
                "run_id": run.run_id,
                "total": run.quote_snapshot["total"] if run.quote_snapshot else None,
            }
            for run in runs
        ],
    }


def build_tools(db: Session) -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=lambda run_id: _get_run_status(db, run_id),
            name="get_run_status",
            description=(
                "Look up a specific RFQ run's current status, buyer, and total by its exact "
                "run ID (e.g. RFQ-1042)."
            ),
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=lambda run_id: _why_run_blocked(db, run_id),
            name="why_run_blocked",
            description="Explain why a specific RFQ run is stuck and what it's waiting on.",
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=lambda run_id: _get_quote_details(db, run_id),
            name="get_quote_details",
            description="Fetch the full quote breakdown and line items for a specific RFQ.",
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=lambda run_id: _get_payment_status(db, run_id),
            name="get_payment_status",
            description="Fetch payment link/payment status for a specific RFQ.",
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=lambda run_id: _get_invoice_status(db, run_id),
            name="get_invoice_status",
            description="Fetch invoice generation and send status for a specific RFQ.",
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=lambda: _get_inventory(db),
            name="get_inventory",
            description=(
                "List every product in the catalogue with its SKU, unit price, and current "
                "stock quantity. Owned by the Stock Desk."
            ),
        ),
        StructuredTool.from_function(
            func=lambda: _get_low_stock_items(db),
            name="get_low_stock_items",
            description=(
                "List products currently at or below their reorder threshold. "
                "Owned by the Stock Desk."
            ),
        ),
        StructuredTool.from_function(
            func=lambda: _get_pending_payments(db),
            name="get_pending_payments",
            description=(
                "List runs where a payment link was sent but payment isn't confirmed yet. "
                "Owned by the Accounts Desk."
            ),
        ),
        StructuredTool.from_function(
            func=lambda: _get_open_quotes_today(db),
            name="get_open_quotes_today",
            description=(
                "List quotes sent to buyers today that are still open. Owned by the Sales Desk."
            ),
        ),
        StructuredTool.from_function(
            func=lambda query: _get_recent_customer_activity(db, query),
            name="get_recent_customer_activity",
            description=(
                "Search a buyer and summarize recent runs, open quotes, and pending actions."
            ),
            args_schema=CustomerSearchInput,
        ),
        StructuredTool.from_function(
            func=lambda: _get_vendor_updates(db),
            name="get_vendor_updates",
            description="List recent supplier price, stock, and delay updates.",
        ),
        StructuredTool.from_function(
            func=lambda: _get_daily_summary(db),
            name="get_daily_summary",
            description="Summarize open quotes, low stock, pending payments, and urgent blockers.",
        ),
        StructuredTool.from_function(
            func=lambda run_id: _get_run_timeline(db, run_id),
            name="get_run_timeline",
            description="Return the event trail for a specific RFQ/order.",
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=lambda: _get_orders_in_progress(db),
            name="get_orders_in_progress",
            description="List accepted, paid, invoiced, and in-progress orders.",
        ),
        StructuredTool.from_function(
            func=lambda: _get_reminders_due(db),
            name="get_reminders_due",
            description="List reminders due today.",
        ),
        StructuredTool.from_function(
            func=lambda query: _search_customer(db, query),
            name="search_customer",
            description="Search buyers by phone number, name, or business text.",
            args_schema=CustomerSearchInput,
        ),
        StructuredTool.from_function(
            func=lambda: _get_business_team(),
            name="get_business_team",
            description="Show the Manager-led desk and specialist-agent structure.",
        ),
        StructuredTool.from_function(
            func=lambda: _get_mvp_team(),
            name="get_mvp_team",
            description="Show only the currently recommended MVP desks and specialist agents.",
        ),
        StructuredTool.from_function(
            func=lambda text: _preview_commerce_conversation(text),
            name="preview_commerce_agent_conversation",
            description=(
                "Preview how Commerce Desk agents pass a buyer request between each other. "
                "Read-only; does not create a run, quote, payment, or invoice."
            ),
            args_schema=TextInput,
        ),
        StructuredTool.from_function(
            func=lambda: _preview_daily_summary_conversation(db),
            name="preview_daily_summary_agent_conversation",
            description=(
                "Preview how Daily Summary and Audit agents coordinate on today's summary. "
                "Read-only; does not mutate reminders, approvals, or runs."
            ),
        ),
    ]
