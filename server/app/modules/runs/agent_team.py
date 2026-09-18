"""Manager-led business team registry.

The owner/admin still talks to one Principal Manager. These desk agents are
internal capabilities the Manager can route to or summarize from; they are not
independent chatbots and they do not bypass deterministic commerce rules.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from app.modules.runs import mock_desks
from app.modules.runs.state_machine import RunStatus


class DeskId(StrEnum):
    PRINCIPAL_MANAGER = "principal_manager"
    COMMERCE = "commerce"
    OPERATIONS = "operations"
    OFFICE = "office"
    GROWTH = "growth"
    AUDIT = "audit"


class AgentId(StrEnum):
    PRINCIPAL_MANAGER = "principal_manager"
    CUSTOMER_INTAKE = "customer_intake_agent"
    CATALOG_SKU = "catalog_sku_agent"
    INVENTORY = "inventory_agent"
    PRICING = "pricing_agent"
    QUOTE = "quote_agent"
    PAYMENT = "payment_agent"
    INVOICE = "invoice_agent"
    REMINDER = "reminder_agent"
    DELIVERY_DISPATCH = "delivery_dispatch_agent"
    VENDOR_COORDINATION = "vendor_coordination_agent"
    PURCHASE_FOLLOWUP = "purchase_followup_agent"
    RETURN_ISSUE = "return_issue_agent"
    EMAIL = "email_agent"
    CALENDAR_MEETING = "calendar_meeting_agent"
    SPREADSHEET_REPORTING = "spreadsheet_reporting_agent"
    DAILY_SUMMARY = "daily_summary_agent"
    TASK_TRACKER = "task_tracker_agent"
    CREATIVE_STRATEGY = "creative_strategy_agent"
    COPYWRITER = "copywriter_agent"
    INSTAGRAM_STORY = "instagram_story_agent"
    PRODUCT_CONTENT = "product_content_agent"
    CAMPAIGN = "campaign_agent"
    APPROVAL_GUARD = "approval_guard_agent"
    AUDIT_TRAIL = "audit_trail_agent"
    POLICY_COMPLIANCE = "policy_compliance_agent"
    ANALYTICS = "analytics_agent"


@dataclass(frozen=True)
class DeskAgent:
    id: AgentId
    name: str
    desk: DeskId
    summary: str
    permissions: tuple[str, ...]
    deterministic_only: bool = False
    mvp: bool = True


@dataclass(frozen=True)
class Desk:
    id: DeskId
    name: str
    summary: str
    agents: tuple[AgentId, ...]


@dataclass(frozen=True)
class AgentTurn:
    from_agent: AgentId
    to_agent: AgentId
    message: str
    payload: dict[str, Any]


AgentHandler = Callable[[dict[str, Any]], dict[str, Any]]

AGENTCRAFT_AGENT_IDS_BY_NAME = {
    "Principal Manager": "manager",
    "Customer Intake Agent": "sales",
    "Catalog/SKU Agent": "sales",
    "Inventory Agent": "inventory",
    "Pricing Agent": "pricing",
    "Quote Agent": "sales",
    "Payment Agent": "accounts",
    "Invoice Agent": "accounts",
    "Daily Summary Agent": "assistant-claude",
    "Approval Guard Agent": "qa",
    "Audit Trail Agent": "qa",
    "Policy/Compliance Agent": "qa",
}

AGENTCRAFT_AGENT_IDS_BY_ROLE = {
    "Manager": "manager",
    "Sales Desk": "sales",
    "Stock Desk": "inventory",
    "Pricing Desk": "pricing",
    "Accounts Desk": "accounts",
    "Invoice Desk": "accounts",
    "Audit Desk": "qa",
}


AGENTS: dict[AgentId, DeskAgent] = {
    AgentId.PRINCIPAL_MANAGER: DeskAgent(
        AgentId.PRINCIPAL_MANAGER,
        "Principal Manager",
        DeskId.PRINCIPAL_MANAGER,
        "Owner-facing control point that delegates to specialized desks.",
        ("read_business_state", "delegate", "summarize", "request_exact_commands"),
    ),
    AgentId.CUSTOMER_INTAKE: DeskAgent(
        AgentId.CUSTOMER_INTAKE,
        "Customer Intake Agent",
        DeskId.COMMERCE,
        "Normalizes buyer messages and detects intent, content type, and urgency.",
        ("classify_buyer_message", "extract_requested_items"),
        deterministic_only=True,
    ),
    AgentId.CATALOG_SKU: DeskAgent(
        AgentId.CATALOG_SKU,
        "Catalog/SKU Agent",
        DeskId.COMMERCE,
        "Maps informal item names to catalogue SKUs and flags ambiguity.",
        ("match_line_items", "resolve_skus"),
        deterministic_only=True,
    ),
    AgentId.INVENTORY: DeskAgent(
        AgentId.INVENTORY,
        "Inventory Agent",
        DeskId.COMMERCE,
        "Checks stock and low-stock status without permanently mutating inventory.",
        ("check_inventory", "suggest_substitutes"),
        deterministic_only=True,
    ),
    AgentId.PRICING: DeskAgent(
        AgentId.PRICING,
        "Pricing Agent",
        DeskId.COMMERCE,
        "Calculates quote totals, tax, and approval threshold reasons.",
        ("calculate_quote", "check_margin_policy"),
        deterministic_only=True,
    ),
    AgentId.QUOTE: DeskAgent(
        AgentId.QUOTE,
        "Quote Agent",
        DeskId.COMMERCE,
        "Turns priced line items into buyer-facing quote summaries/artifacts.",
        ("create_quote_artifact",),
        deterministic_only=True,
    ),
    AgentId.PAYMENT: DeskAgent(
        AgentId.PAYMENT,
        "Payment Agent",
        DeskId.COMMERCE,
        "Creates/resends payment links and reads provider-verified payment status.",
        ("create_payment_link", "get_payment_status", "verify_payment_webhook"),
        deterministic_only=True,
    ),
    AgentId.INVOICE: DeskAgent(
        AgentId.INVOICE,
        "Invoice Agent",
        DeskId.COMMERCE,
        "Creates and resends invoices only after verified payment.",
        ("create_invoice", "get_invoice_status", "send_invoice_document"),
        deterministic_only=True,
    ),
    AgentId.REMINDER: DeskAgent(
        AgentId.REMINDER,
        "Reminder Agent",
        DeskId.OPERATIONS,
        "Tracks run-linked reminders and follow-ups.",
        ("create_reminder", "list_reminders", "complete_reminder"),
    ),
    AgentId.DELIVERY_DISPATCH: DeskAgent(
        AgentId.DELIVERY_DISPATCH,
        "Delivery/Dispatch Agent",
        DeskId.OPERATIONS,
        "Coordinates delivery location, dispatch slot, and delivery updates.",
        ("collect_delivery_location", "send_delivery_update"),
        mvp=False,
    ),
    AgentId.VENDOR_COORDINATION: DeskAgent(
        AgentId.VENDOR_COORDINATION,
        "Vendor Coordination Agent",
        DeskId.OPERATIONS,
        "Records supplier stock, delay, and price updates.",
        ("record_vendor_stock_update", "record_vendor_delay", "request_vendor_quote"),
    ),
    AgentId.PURCHASE_FOLLOWUP: DeskAgent(
        AgentId.PURCHASE_FOLLOWUP,
        "Purchase Follow-up Agent",
        DeskId.OPERATIONS,
        "Chases PO, payment, dispatch, and incomplete order follow-ups.",
        ("schedule_payment_followup", "schedule_delivery_followup"),
        mvp=False,
    ),
    AgentId.RETURN_ISSUE: DeskAgent(
        AgentId.RETURN_ISSUE,
        "Return/Issue Agent",
        DeskId.OPERATIONS,
        "Routes damaged/wrong item complaints to a controlled support flow.",
        ("record_issue", "escalate_issue"),
        mvp=False,
    ),
    AgentId.EMAIL: DeskAgent(
        AgentId.EMAIL,
        "Email Agent",
        DeskId.OFFICE,
        "Reads, drafts, and sends important business emails.",
        ("read_recent_emails", "draft_email", "send_email"),
    ),
    AgentId.CALENDAR_MEETING: DeskAgent(
        AgentId.CALENDAR_MEETING,
        "Calendar/Meeting Agent",
        DeskId.OFFICE,
        "Books supplier calls, meetings, site visits, and owner calendar blocks.",
        ("create_calendar_event", "list_calendar_events", "update_calendar_event"),
        mvp=False,
    ),
    AgentId.SPREADSHEET_REPORTING: DeskAgent(
        AgentId.SPREADSHEET_REPORTING,
        "Spreadsheet/Reporting Agent",
        DeskId.OFFICE,
        "Appends quotes/payments/invoices and exports SMB-friendly reports.",
        ("append_quote_to_sheet", "append_payment_to_sheet", "append_invoice_to_sheet"),
    ),
    AgentId.DAILY_SUMMARY: DeskAgent(
        AgentId.DAILY_SUMMARY,
        "Daily Summary Agent",
        DeskId.OFFICE,
        "Formats open quotes, pending payments, low stock, blockers, and reminders.",
        ("get_daily_summary",),
    ),
    AgentId.TASK_TRACKER: DeskAgent(
        AgentId.TASK_TRACKER,
        "Task Tracker Agent",
        DeskId.OFFICE,
        "Tracks owner to-dos and run-linked task completion.",
        ("create_task", "list_tasks", "complete_task"),
        mvp=False,
    ),
    AgentId.CREATIVE_STRATEGY: DeskAgent(
        AgentId.CREATIVE_STRATEGY,
        "Creative Strategy Agent",
        DeskId.GROWTH,
        "Chooses story, poster, promo copy, or campaign direction.",
        ("plan_campaign_asset",),
        mvp=False,
    ),
    AgentId.COPYWRITER: DeskAgent(
        AgentId.COPYWRITER,
        "Copywriter Agent",
        DeskId.GROWTH,
        "Drafts captions, WhatsApp promos, reminders, and offer copy.",
        ("draft_copy",),
        mvp=False,
    ),
    AgentId.INSTAGRAM_STORY: DeskAgent(
        AgentId.INSTAGRAM_STORY,
        "Instagram Story Agent",
        DeskId.GROWTH,
        "Creates story-ready frame copy, CTA, and visual directions.",
        ("draft_instagram_story",),
        mvp=False,
    ),
    AgentId.PRODUCT_CONTENT: DeskAgent(
        AgentId.PRODUCT_CONTENT,
        "Product Content Agent",
        DeskId.GROWTH,
        "Cleans product titles and creates short product descriptions.",
        ("draft_product_content",),
        mvp=False,
    ),
    AgentId.CAMPAIGN: DeskAgent(
        AgentId.CAMPAIGN,
        "Campaign Agent",
        DeskId.GROWTH,
        "Coordinates seasonal, top-SKU, repeat-buyer, and reorder campaigns.",
        ("plan_campaign",),
        mvp=False,
    ),
    AgentId.APPROVAL_GUARD: DeskAgent(
        AgentId.APPROVAL_GUARD,
        "Approval Guard Agent",
        DeskId.AUDIT,
        "Protects exact run/version approval and risky command boundaries.",
        ("verify_approval_token", "validate_admin_actor"),
        deterministic_only=True,
    ),
    AgentId.AUDIT_TRAIL: DeskAgent(
        AgentId.AUDIT_TRAIL,
        "Audit Trail Agent",
        DeskId.AUDIT,
        "Records who triggered what and why for trust, debugging, and compliance.",
        ("record_audit_event", "get_audit_trail"),
        deterministic_only=True,
    ),
    AgentId.POLICY_COMPLIANCE: DeskAgent(
        AgentId.POLICY_COMPLIANCE,
        "Policy/Compliance Agent",
        DeskId.AUDIT,
        "Checks pricing, payment, invoice, retention, and permission guardrails.",
        ("check_margin_policy", "verify_payment_signature", "check_idempotency_key"),
        deterministic_only=True,
    ),
    AgentId.ANALYTICS: DeskAgent(
        AgentId.ANALYTICS,
        "Analytics Agent",
        DeskId.AUDIT,
        "Summarizes conversion, payment completion, stock, and delay signals.",
        ("export_day_report",),
        mvp=False,
    ),
}


DESKS: dict[DeskId, Desk] = {
    DeskId.PRINCIPAL_MANAGER: Desk(
        DeskId.PRINCIPAL_MANAGER,
        "Principal Manager",
        "The only owner/admin-facing brain.",
        (AgentId.PRINCIPAL_MANAGER,),
    ),
    DeskId.COMMERCE: Desk(
        DeskId.COMMERCE,
        "Commerce Desk",
        "Customer quote, order, payment, and invoice flow.",
        (
            AgentId.CUSTOMER_INTAKE,
            AgentId.CATALOG_SKU,
            AgentId.INVENTORY,
            AgentId.PRICING,
            AgentId.QUOTE,
            AgentId.PAYMENT,
            AgentId.INVOICE,
        ),
    ),
    DeskId.OPERATIONS: Desk(
        DeskId.OPERATIONS,
        "Operations Desk",
        "Reminders, delivery, vendor coordination, and issue resolution.",
        (
            AgentId.REMINDER,
            AgentId.DELIVERY_DISPATCH,
            AgentId.VENDOR_COORDINATION,
            AgentId.PURCHASE_FOLLOWUP,
            AgentId.RETURN_ISSUE,
        ),
    ),
    DeskId.OFFICE: Desk(
        DeskId.OFFICE,
        "Office/PA Desk",
        "Email, meetings, summaries, spreadsheets, and owner tasks.",
        (
            AgentId.EMAIL,
            AgentId.CALENDAR_MEETING,
            AgentId.SPREADSHEET_REPORTING,
            AgentId.DAILY_SUMMARY,
            AgentId.TASK_TRACKER,
        ),
    ),
    DeskId.GROWTH: Desk(
        DeskId.GROWTH,
        "Growth Desk",
        "Promotional copy, product content, stories, and campaigns.",
        (
            AgentId.CREATIVE_STRATEGY,
            AgentId.COPYWRITER,
            AgentId.INSTAGRAM_STORY,
            AgentId.PRODUCT_CONTENT,
            AgentId.CAMPAIGN,
        ),
    ),
    DeskId.AUDIT: Desk(
        DeskId.AUDIT,
        "Audit & Control Desk",
        "Approvals, audit trail, policy guardrails, and analytics.",
        (
            AgentId.APPROVAL_GUARD,
            AgentId.AUDIT_TRAIL,
            AgentId.POLICY_COMPLIANCE,
            AgentId.ANALYTICS,
        ),
    ),
}


def list_desks(*, mvp_only: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "id": desk.id.value,
            "name": desk.name,
            "summary": desk.summary,
            "agents": [
                AGENTS[agent_id].name
                for agent_id in desk.agents
                if not mvp_only or AGENTS[agent_id].mvp
            ],
        }
        for desk in DESKS.values()
    ]


def list_agents(*, mvp_only: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "id": agent.id.value,
            "name": agent.name,
            "desk": DESKS[agent.desk].name,
            "summary": agent.summary,
            "permissions": list(agent.permissions),
            "deterministic_only": agent.deterministic_only,
            "mvp": agent.mvp,
        }
        for agent in AGENTS.values()
        if not mvp_only or agent.mvp
    ]


def _customer_intake(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "")
    return {
        "actor": payload.get("actor", "buyer"),
        "intent": payload.get("intent", "new_order"),
        "content_type": payload.get("content_type", "text"),
        "normalized_text": " ".join(text.split()),
        "requested_output_mode": payload.get("requested_output_mode", "text"),
    }


def _catalog_sku(payload: dict[str, Any]) -> dict[str, Any]:
    return {"line_items": mock_desks.match_line_items(str(payload.get("text") or ""))}


def _inventory(payload: dict[str, Any]) -> dict[str, Any]:
    return {"line_items": mock_desks.check_stock(payload.get("line_items", []))}


def _pricing(payload: dict[str, Any]) -> dict[str, Any]:
    return {"quote": mock_desks.quote(payload.get("line_items", []))}


def _quote(payload: dict[str, Any]) -> dict[str, Any]:
    quote = payload.get("quote") or {}
    return {
        "quote_summary": {
            "total": quote.get("total"),
            "currency": quote.get("currency", "INR"),
            "approval_required": quote.get("approval_required", False),
            "reason_codes": quote.get("reason_codes", []),
        }
    }


def _payment(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or "RFQ-UNKNOWN")
    number = run_id.split("-")[-1]
    return {
        "payment": {
            "payment_id": payload.get("payment_id") or f"pay_{number}",
            "provider": "mock",
            "status": payload.get("status") or RunStatus.PAYMENT_PENDING.value,
            "payment_url": f"https://pay.stockaware.test/pay_{number}",
        }
    }


def _invoice(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or "RFQ-UNKNOWN")
    number = run_id.split("-")[-1]
    return {
        "invoice": {
            "invoice_number": payload.get("invoice_id") or f"INV-{number}",
            "status": "GENERATED",
            "artifact_key": f"invoices/{run_id}/INV-{number}.pdf",
        }
    }


def _placeholder(agent_id: AgentId) -> AgentHandler:
    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        agent = AGENTS[agent_id]
        return {
            "agent": agent.name,
            "desk": DESKS[agent.desk].name,
            "status": "READY_NOT_CONNECTED",
            "accepted_payload": payload,
        }

    return handler


HANDLERS: dict[AgentId, AgentHandler] = {
    AgentId.CUSTOMER_INTAKE: _customer_intake,
    AgentId.CATALOG_SKU: _catalog_sku,
    AgentId.INVENTORY: _inventory,
    AgentId.PRICING: _pricing,
    AgentId.QUOTE: _quote,
    AgentId.PAYMENT: _payment,
    AgentId.INVOICE: _invoice,
}


def delegate_to_agent(agent_id: AgentId | str, payload: dict[str, Any]) -> dict[str, Any]:
    resolved = AgentId(agent_id)
    handler = HANDLERS.get(resolved, _placeholder(resolved))
    return {
        "agent": AGENTS[resolved].name,
        "desk": DESKS[AGENTS[resolved].desk].name,
        "result": handler(payload),
    }


def _turn(
    from_agent: AgentId,
    to_agent: AgentId,
    message: str,
    payload: dict[str, Any],
) -> AgentTurn:
    return AgentTurn(from_agent, to_agent, message, payload)


def _public_turn(turn: AgentTurn) -> dict[str, Any]:
    return {
        "from": AGENTS[turn.from_agent].name,
        "to": AGENTS[turn.to_agent].name,
        "message": turn.message,
        "payload": turn.payload,
    }


def run_commerce_conversation(text: str, *, content_type: str = "text") -> dict[str, Any]:
    """Run a controlled agent-to-agent quote workflow.

    This is a deterministic conversation: each agent receives the previous
    agent's structured output, adds its own facts, and passes them forward.
    """
    transcript: list[AgentTurn] = []

    intake_in = {"text": text, "content_type": content_type}
    transcript.append(
        _turn(
            AgentId.PRINCIPAL_MANAGER,
            AgentId.CUSTOMER_INTAKE,
            "Normalize this buyer request for the Commerce Desk.",
            intake_in,
        )
    )
    intake = delegate_to_agent(AgentId.CUSTOMER_INTAKE, intake_in)["result"]
    transcript.append(
        _turn(
            AgentId.CUSTOMER_INTAKE,
            AgentId.CATALOG_SKU,
            "Here is the normalized request. Match it to catalogue SKUs.",
            {**intake, "text": intake["normalized_text"]},
        )
    )

    catalog = delegate_to_agent(AgentId.CATALOG_SKU, {"text": intake["normalized_text"]})["result"]
    unresolved = [item for item in catalog["line_items"] if item.get("match_status") != "MATCHED"]
    if unresolved:
        transcript.append(
            _turn(
                AgentId.CATALOG_SKU,
                AgentId.PRINCIPAL_MANAGER,
                "I found unresolved catalogue items. Ask the buyer for clarification.",
                {"unresolved_items": unresolved},
            )
        )
        return {
            "workflow": "commerce_quote",
            "status": "NEEDS_CLARIFICATION",
            "transcript": [_public_turn(turn) for turn in transcript],
            "result": {"unresolved_items": unresolved},
        }

    transcript.append(
        _turn(
            AgentId.CATALOG_SKU,
            AgentId.INVENTORY,
            "Catalogue items are matched. Check stock without reserving inventory.",
            catalog,
        )
    )
    inventory = delegate_to_agent(AgentId.INVENTORY, catalog)["result"]

    transcript.append(
        _turn(
            AgentId.INVENTORY,
            AgentId.PRICING,
            "Stock check is ready. Calculate quote and approval reasons.",
            inventory,
        )
    )
    pricing = delegate_to_agent(AgentId.PRICING, inventory)["result"]

    transcript.append(
        _turn(
            AgentId.PRICING,
            AgentId.QUOTE,
            "Pricing is ready. Prepare the quote summary for the Manager.",
            pricing,
        )
    )
    quote = delegate_to_agent(AgentId.QUOTE, pricing)["result"]

    next_agent = (
        AgentId.APPROVAL_GUARD
        if quote["quote_summary"]["approval_required"]
        else AgentId.PRINCIPAL_MANAGER
    )
    transcript.append(
        _turn(
            AgentId.QUOTE,
            next_agent,
            "Quote summary is ready. Decide whether owner approval is needed.",
            quote,
        )
    )

    return {
        "workflow": "commerce_quote",
        "status": "APPROVAL_REQUIRED"
        if quote["quote_summary"]["approval_required"]
        else "READY_TO_SEND",
        "transcript": [_public_turn(turn) for turn in transcript],
        "result": {**pricing, **quote},
    }


def run_daily_summary_conversation(summary: dict[str, Any]) -> dict[str, Any]:
    transcript = [
        _turn(
            AgentId.PRINCIPAL_MANAGER,
            AgentId.DAILY_SUMMARY,
            "Format today's operating facts into an owner-ready summary.",
            summary,
        )
    ]
    blockers = summary.get("urgent_blockers", [])
    if blockers:
        transcript.append(
            _turn(
                AgentId.DAILY_SUMMARY,
                AgentId.APPROVAL_GUARD,
                "There are blockers. Check whether any need owner approval guardrails.",
                {"urgent_blockers": blockers},
            )
        )
        transcript.append(
            _turn(
                AgentId.APPROVAL_GUARD,
                AgentId.PRINCIPAL_MANAGER,
                "Blockers reviewed. Use exact commands for risky actions.",
                {"requires_exact_commands": True, "urgent_blockers": blockers},
            )
        )
    else:
        transcript.append(
            _turn(
                AgentId.DAILY_SUMMARY,
                AgentId.PRINCIPAL_MANAGER,
                "No urgent blockers found. Send the short summary.",
                {"requires_exact_commands": False},
            )
        )

    return {
        "workflow": "daily_summary",
        "status": "READY",
        "transcript": [_public_turn(turn) for turn in transcript],
        "result": {
            "open_quotes_count": len(summary.get("open_quotes", [])),
            "pending_payments_count": len(summary.get("pending_payments", [])),
            "low_stock_count": len(summary.get("low_stock", [])),
            "urgent_blockers_count": len(blockers),
        },
    }


def agentcraft_events_from_transcript(
    *,
    run_id: str,
    transcript: list[dict[str, Any]],
    started_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Convert backend agent turns to the frontend AgentCraft event contract."""
    base_time = started_at or datetime.now(UTC)
    events = []
    for index, turn in enumerate(transcript):
        from_agent = AGENTCRAFT_AGENT_IDS_BY_NAME.get(turn["from"])
        to_agent = AGENTCRAFT_AGENT_IDS_BY_NAME.get(turn["to"])
        if not from_agent or not to_agent or from_agent == to_agent:
            continue
        message = str(turn.get("message") or "")
        is_result = to_agent == "manager"
        status = "waiting" if "approval" in message.casefold() else "working"
        if is_result:
            status = "blocked" if "clarification" in message.casefold() else "completed"
        events.append(
            {
                "run_id": run_id,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "type": "result" if is_result else "task",
                "message": message,
                "status": status,
                "timestamp": (base_time + timedelta(seconds=index * 3)).isoformat(),
            }
        )
    return events


def run_agentcraft_commerce_events(
    *,
    run_id: str,
    text: str,
    started_at: datetime | None = None,
) -> list[dict[str, Any]]:
    conversation = run_commerce_conversation(text)
    return agentcraft_events_from_transcript(
        run_id=run_id,
        transcript=conversation["transcript"],
        started_at=started_at,
    )


def agentcraft_events_from_run_events(
    *, run_id: str, run_events: list[Any]
) -> list[dict[str, Any]]:
    """Convert actual persisted run timeline events to AgentCraft events."""
    events = []
    previous_agent = "manager"
    for event in run_events:
        to_agent = AGENTCRAFT_AGENT_IDS_BY_ROLE.get(event.role, "manager")
        if to_agent == previous_agent:
            continue
        status = "working"
        event_text = event.event.casefold()
        if "approval" in event_text:
            status = "waiting"
        elif "could not" in event_text or "low stock" in event_text:
            status = "blocked"
        elif "sent" in event_text or "created" in event_text or "confirmed" in event_text:
            status = "completed"
        events.append(
            {
                "run_id": run_id,
                "from_agent": previous_agent,
                "to_agent": to_agent,
                "type": "result" if to_agent == "manager" else "task",
                "message": event.event,
                "status": status,
                "timestamp": event.created_at.isoformat(),
            }
        )
        previous_agent = to_agent
    return events
