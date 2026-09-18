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
from app.modules.runs.repository import get_run_by_run_id, list_runs
from app.modules.runs.state_machine import RunStatus


class RunIdInput(BaseModel):
    run_id: str = Field(description="The exact RFQ run ID, e.g. RFQ-1042")


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
    ]
