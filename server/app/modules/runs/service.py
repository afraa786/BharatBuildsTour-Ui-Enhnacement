import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.runs import mock_desks
from app.modules.runs.intent_router import ActorType, IntentType, route_message
from app.modules.runs.models import Run
from app.modules.runs.repository import (
    add_event,
    create_approval,
    create_run,
    get_open_run_for_buyer,
    get_pending_approval,
    get_run_by_run_id,
    get_timeline,
    list_runs,
)
from app.modules.runs.state_machine import RunStatus, assert_valid_transition

_APPROVE_RE = re.compile(r"^approve\s+(rfq-\S+)$", re.IGNORECASE)
_REJECT_RE = re.compile(r"^reject\s+(rfq-\S+)$", re.IGNORECASE)
_SHOW_RE = re.compile(r"^show\s+(rfq-\S+)$", re.IGNORECASE)
_WHY_RE = re.compile(r"^why\s+was\s+(rfq-\S+)\s+blocked\??$", re.IGNORECASE)
_OPEN_QUOTES_RE = re.compile(r"^show\s+open\s+quotes\s+today$", re.IGNORECASE)

HELP_TEXT = (
    "Sorry, I didn't recognize that command. Try: Approve RFQ-1042, "
    "Reject RFQ-1042, Show RFQ-1042, Why was RFQ-1042 blocked?, "
    "Show open quotes today"
)


@dataclass
class OutboundMessage:
    to: str
    text: str = ""
    message_type: str = "text"
    media_id: str | None = None
    link: str | None = None
    caption: str | None = None
    filename: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    name: str | None = None
    address: str | None = None
    contacts: list[dict] = field(default_factory=list)
    interactive: dict | None = None


def _transition(
    db: Session, run: Run, target: RunStatus, role: str, event: str, metadata: dict | None = None
) -> None:
    assert_valid_transition(RunStatus(run.status), target)
    run.status = target.value
    run.version += 1
    add_event(db, run, role, event, metadata)


def _quote_number(run: Run) -> str:
    return f"Q-{run.run_id.split('-')[1]}-V1"


def _clarification_text(unresolved: list[dict]) -> str:
    lines = ["I couldn't match a few items to our catalogue:"]
    for item in unresolved:
        requested = item["requested_text"]
        if item["match_status"] == "AMBIGUOUS":
            lines.append(
                f'- "{requested}" matched more than one product, can you confirm the exact item?'
            )
        else:
            lines.append(
                f'- "{requested}" not in our catalogue, could you clarify or spell it differently?'
            )
    return "\n".join(lines)


def _quote_text(run: Run, snapshot: dict) -> str:
    lines = [f"Quote for {run.run_id}:"]
    for item in snapshot["items"]:
        qty, unit, price, total = (
            item["quantity"],
            item["unit"],
            item["unit_price"],
            item["line_total"],
        )
        lines.append(f"- {item['name']} x{qty} {unit} @ ₹{price} = ₹{total}")
    lines.append(f"Subtotal: ₹{snapshot['subtotal']}")
    lines.append(f"GST: ₹{snapshot['tax']}")
    lines.append(f"Total: ₹{snapshot['total']}")
    lines.append('Reply "accept" to proceed to payment, or tell us what to change.')
    return "\n".join(lines)


def _admin_approval_prompt(run: Run, snapshot: dict) -> str:
    reasons = ", ".join(snapshot["reason_codes"]) or "policy check"
    return (
        f"{run.run_id} needs approval ({reasons}).\n"
        f"Buyer: {run.buyer_wa_id}\nTotal: ₹{snapshot['total']}\n"
        f'Reply "Approve {run.run_id}" or "Reject {run.run_id}".'
    )


def _run_pipeline(db: Session, run: Run, text_body: str) -> list[OutboundMessage]:
    """Normalize -> stock -> price -> approval/quote. Used for new runs and clarifications."""
    outbound: list[OutboundMessage] = []
    settings = get_settings()

    line_items = mock_desks.match_line_items(text_body)
    run.line_items = line_items
    add_event(db, run, "Stock Desk", "Parsed line items", {"line_items": line_items})

    unresolved = [i for i in line_items if i["match_status"] != "MATCHED"]
    if unresolved:
        _transition(
            db,
            run,
            RunStatus.WAITING_FOR_CLARIFICATION,
            "Sales Desk",
            "Could not match all items",
            {"unresolved": unresolved},
        )
        outbound.append(OutboundMessage(run.buyer_wa_id, _clarification_text(unresolved)))
        return outbound

    _transition(db, run, RunStatus.CHECKING_STOCK, "Stock Desk", "Checking stock")
    checked = mock_desks.check_stock(line_items)
    run.line_items = checked
    low_stock = [i for i in checked if i.get("low_stock")]
    if low_stock:
        add_event(
            db, run, "Stock Desk", "Low stock flagged", {"skus": [i["sku"] for i in low_stock]}
        )

    _transition(db, run, RunStatus.CHECKING_PRICE, "Pricing Desk", "Calculating quote")
    snapshot = mock_desks.quote(checked)
    run.quote_snapshot = snapshot

    if snapshot["approval_required"]:
        _transition(
            db,
            run,
            RunStatus.APPROVAL_PENDING,
            "Pricing Desk",
            "Approval required",
            {"reason_codes": snapshot["reason_codes"]},
        )
        create_approval(db, run)
        outbound.append(
            OutboundMessage(
                run.buyer_wa_id,
                "Thanks! Your request needs a quick check from our team, we'll confirm shortly.",
            )
        )
        for admin_wa_id in settings.admin_wa_ids:
            outbound.append(OutboundMessage(admin_wa_id, _admin_approval_prompt(run, snapshot)))
    else:
        _transition(db, run, RunStatus.QUOTE_CREATED, "Pricing Desk", "Quote created")
        run.quote_id = _quote_number(run)
        _transition(db, run, RunStatus.QUOTE_SENT, "Sales Desk", "Quote sent to buyer")
        outbound.append(OutboundMessage(run.buyer_wa_id, _quote_text(run, snapshot)))

    return outbound


def _payment_link_text(run: Run) -> str:
    payment_id = run.payment_id or f"pay_{run.run_id.split('-')[1]}"
    total = run.quote_snapshot["total"] if run.quote_snapshot else "0.00"
    link = f"https://pay.stockaware.test/{payment_id}"
    return f"Complete payment here (mock link): {link} for ₹{total}"


def _invoice_text(run: Run) -> str:
    invoice_id = run.invoice_id or f"INV-{run.run_id.split('-')[1]}"
    return (
        f"Your invoice {invoice_id} is ready. Reply if you want it sent again by email or WhatsApp."
    )


def _important_updates_text(db: Session | None) -> str:
    if db is None:
        return (
            "I can help with operational updates. Try: Show open quotes today, show low stock, "
            "or show pending payments."
        )
    return _open_quotes_today_text(db)


def _vendor_update_text(intent: IntentType, vendor_wa_id: str) -> str:
    if intent is IntentType.VENDOR_PRICE_REVISION:
        return (
            f"Vendor update from {vendor_wa_id}: revised pricing received. "
            "Review affected open quotes."
        )
    if intent is IntentType.VENDOR_DELAY_NOTICE:
        return f"Vendor update from {vendor_wa_id}: delivery or dispatch delay reported."
    if intent is IntentType.VENDOR_STOCK_UPDATE:
        return f"Vendor update from {vendor_wa_id}: stock availability update received."
    return f"Vendor update from {vendor_wa_id}: new supplier message received."


def process_buyer_message(db: Session, buyer_wa_id: str, text_body: str) -> list[OutboundMessage]:
    run = get_open_run_for_buyer(db, buyer_wa_id)

    if run is None:
        run = create_run(db, buyer_wa_id, buyer_name=None, raw_text=text_body)
        add_event(db, run, "Manager", "Run received from WhatsApp", {"text": text_body})
        _transition(db, run, RunStatus.NORMALIZING, "Manager", "Normalizing buyer request")
        return _run_pipeline(db, run, text_body)

    current = RunStatus(run.status)
    decision = route_message(
        text_body,
        actor_hint=ActorType.BUYER,
        current_status=current.value,
        wa_id=buyer_wa_id,
    )

    if current == RunStatus.WAITING_FOR_CLARIFICATION:
        run.raw_text = f"{run.raw_text} {text_body}"
        _transition(db, run, RunStatus.NORMALIZING, "Manager", "Received clarification")
        return _run_pipeline(db, run, run.raw_text)

    if current == RunStatus.QUOTE_SENT:
        if decision.intent is IntentType.ACCEPT_QUOTE:
            _transition(db, run, RunStatus.ACCEPTED, "Sales Desk", "Buyer accepted quote")
            run.payment_id = f"pay_{run.run_id.split('-')[1]}"
            _transition(
                db,
                run,
                RunStatus.PAYMENT_LINK_SENT,
                "Accounts Desk",
                "Payment link created (mock)",
            )
            _transition(
                db,
                run,
                RunStatus.PAYMENT_PENDING,
                "Accounts Desk",
                "Awaiting payment confirmation",
            )
            return [OutboundMessage(buyer_wa_id, _payment_link_text(run))]
        if decision.intent is IntentType.NEGOTIATE_PRICE:
            return [
                OutboundMessage(
                    buyer_wa_id,
                    "I can help with that. Tell me the exact quantity or target price "
                    "and I'll revise the quote safely.",
                )
            ]
        run.raw_text = f"{run.raw_text} {text_body}"
        _transition(
            db,
            run,
            RunStatus.CHANGE_REQUESTED,
            "Sales Desk",
            "Buyer requested change",
            {"text": text_body, "intent": decision.intent.value},
        )
        _transition(
            db,
            run,
            RunStatus.NORMALIZING,
            "Manager",
            "Re-normalizing after change request",
        )
        return _run_pipeline(db, run, run.raw_text)

    if current in {RunStatus.PAYMENT_LINK_SENT, RunStatus.PAYMENT_PENDING}:
        if decision.intent is IntentType.PAYMENT_CLAIM:
            add_event(db, run, "Accounts Desk", "Buyer claimed payment", {"text": text_body})
            return [
                OutboundMessage(
                    buyer_wa_id,
                    "Thanks — I have noted your payment update. "
                    "We will verify it with the payment provider and confirm shortly.",
                )
            ]
        if decision.intent is IntentType.REQUEST_PAYMENT_LINK:
            return [OutboundMessage(buyer_wa_id, _payment_link_text(run))]
        if decision.intent is IntentType.REQUEST_INVOICE:
            return [
                OutboundMessage(
                    buyer_wa_id,
                    "I'll send the invoice as soon as payment is verified. "
                    "If you've already paid, we are checking it now.",
                )
            ]

    completed_states = {
        RunStatus.PAYMENT_CONFIRMED,
        RunStatus.INVOICE_GENERATED,
        RunStatus.ORDER_CONFIRMED,
    }
    if current in completed_states:
        if decision.intent is IntentType.REQUEST_INVOICE:
            return [OutboundMessage(buyer_wa_id, _invoice_text(run))]

    add_event(
        db,
        run,
        "Manager",
        "Received message in non-actionable state",
        {"text": text_body, "status": current.value, "intent": decision.intent.value},
    )
    return [
        OutboundMessage(
            buyer_wa_id,
            f"Your request {run.run_id} is currently {current.value}. We'll update you soon.",
        )
    ]


def approve_run(db: Session, run_id: str, actor: str) -> list[OutboundMessage]:
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return [OutboundMessage(actor, f"{run_id} not found.")]

    approval = get_pending_approval(db, run)
    if approval is None:
        return [
            OutboundMessage(
                actor, f"{run_id} has no pending approval (current status: {run.status})."
            )
        ]
    if approval.bound_run_version != run.version:
        return [
            OutboundMessage(
                actor, f"{run_id} changed since this approval was requested. Please review again."
            )
        ]
    if approval.expires_at and approval.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        approval.status = "expired"
        _transition(db, run, RunStatus.EXPIRED, "Manager", "Approval expired")
        return [OutboundMessage(actor, f"{run_id} approval window expired.")]

    approval.status = "approved"
    approval.actor = actor
    approval.decided_at = datetime.now(UTC)
    _transition(
        db, run, RunStatus.QUOTE_CREATED, "Manager", "Owner approved quote", {"actor": actor}
    )
    run.quote_id = _quote_number(run)
    _transition(db, run, RunStatus.QUOTE_SENT, "Sales Desk", "Quote sent to buyer")

    return [
        OutboundMessage(run.buyer_wa_id, _quote_text(run, run.quote_snapshot)),
        OutboundMessage(actor, f"Approved. Quote sent to buyer for {run_id}."),
    ]


def reject_run(db: Session, run_id: str, actor: str) -> list[OutboundMessage]:
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return [OutboundMessage(actor, f"{run_id} not found.")]

    approval = get_pending_approval(db, run)
    if approval is None:
        return [
            OutboundMessage(
                actor, f"{run_id} has no pending approval (current status: {run.status})."
            )
        ]
    if approval.bound_run_version != run.version:
        return [
            OutboundMessage(
                actor, f"{run_id} changed since this approval was requested. Please review again."
            )
        ]

    approval.status = "rejected"
    approval.actor = actor
    approval.decided_at = datetime.now(UTC)
    _transition(db, run, RunStatus.REJECTED, "Manager", "Owner rejected quote", {"actor": actor})

    return [
        OutboundMessage(
            run.buyer_wa_id,
            f"Sorry, we can't proceed with {run_id} right now. Our team will follow up.",
        ),
        OutboundMessage(actor, f"Rejected {run_id}."),
    ]


def _show_run_text(db: Session | None, run_id: str) -> str:
    if db is None:
        return (
            f"I need the live run store to show {run_id}. "
            "Open the control room or try again in the connected environment."
        )
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return f"{run_id} not found."
    total = run.quote_snapshot["total"] if run.quote_snapshot else "-"
    return f"{run.run_id} — status: {run.status}\nBuyer: {run.buyer_wa_id}\nTotal: ₹{total}"


def _why_blocked_text(db: Session | None, run_id: str) -> str:
    if db is None:
        return f"I need the live run store to inspect why {run_id} is blocked."
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return f"{run_id} not found."
    if run.status == RunStatus.WAITING_FOR_CLARIFICATION.value:
        unresolved = [i for i in run.line_items if i.get("match_status") != "MATCHED"]
        return f"{run_id} is waiting on buyer clarification for: " + ", ".join(
            i["requested_text"] for i in unresolved
        )
    if run.status == RunStatus.APPROVAL_PENDING.value:
        reasons = (
            ", ".join(run.quote_snapshot.get("reason_codes", []))
            if run.quote_snapshot
            else "unknown"
        )
        return f"{run_id} is waiting on your approval ({reasons})."
    return f"{run_id} is not blocked, current status: {run.status}."


def _open_quotes_today_text(db: Session | None) -> str:
    if db is None:
        return "I need the live run store to summarise open quotes today."
    runs = list_runs(db, status=RunStatus.QUOTE_SENT.value)
    today = datetime.now(UTC).date()
    todays_runs = [r for r in runs if r.created_at.date() == today]
    if not todays_runs:
        return "No open quotes today."
    lines = ["Open quotes today:"]
    for r in todays_runs:
        total = r.quote_snapshot["total"] if r.quote_snapshot else "-"
        lines.append(f"- {r.run_id}: ₹{total}")
    return "\n".join(lines)


def process_admin_message(
    db: Session | None,
    admin_wa_id: str,
    text_body: str,
) -> list[OutboundMessage]:
    stripped = text_body.strip()
    decision = route_message(stripped, actor_hint=ActorType.ADMIN, wa_id=admin_wa_id)

    if m := _APPROVE_RE.match(stripped):
        if db is None:
            return [
                OutboundMessage(
                    admin_wa_id,
                    "Approval actions need the live run store. Reconnect and try again.",
                )
            ]
        return approve_run(db, m.group(1).upper(), actor=admin_wa_id)
    if m := _REJECT_RE.match(stripped):
        if db is None:
            return [
                OutboundMessage(
                    admin_wa_id,
                    "Rejection actions need the live run store. Reconnect and try again.",
                )
            ]
        return reject_run(db, m.group(1).upper(), actor=admin_wa_id)
    if m := _SHOW_RE.match(stripped):
        return [OutboundMessage(admin_wa_id, _show_run_text(db, m.group(1).upper()))]
    if m := _WHY_RE.match(stripped):
        return [OutboundMessage(admin_wa_id, _why_blocked_text(db, m.group(1).upper()))]
    if _OPEN_QUOTES_RE.match(stripped):
        return [OutboundMessage(admin_wa_id, _open_quotes_today_text(db))]

    if decision.intent is IntentType.APPROVE_QUOTE:
        return [
            OutboundMessage(
                admin_wa_id,
                "I found an approval-style message, but I need the exact RFQ ID. "
                "Try: Approve RFQ-1042.",
            )
        ]
    if decision.intent is IntentType.REJECT_QUOTE:
        return [
            OutboundMessage(
                admin_wa_id,
                "I found a rejection-style message, but I need the exact RFQ ID. "
                "Try: Reject RFQ-1042.",
            )
        ]
    if decision.intent is IntentType.IMPORTANT_UPDATES:
        return [OutboundMessage(admin_wa_id, _important_updates_text(db))]
    if decision.intent is IntentType.SHOW_LOW_STOCK:
        return [
            OutboundMessage(
                admin_wa_id,
                "Low-stock signals are available in the control room. "
                "Use 'show low stock' in the demo APIs or open the inventory alerts panel.",
            )
        ]
    if decision.intent is IntentType.SHOW_PENDING_PAYMENTS:
        return [
            OutboundMessage(
                admin_wa_id,
                "Pending payments are tracked in Accounts Desk. "
                "Open the payments queue or ask for the daily summary.",
            )
        ]

    return [OutboundMessage(admin_wa_id, HELP_TEXT)]


def process_vendor_message(
    db: Session | None,
    vendor_wa_id: str,
    text_body: str,
) -> list[OutboundMessage]:
    settings = get_settings()
    decision = route_message(
        text_body,
        actor_hint=ActorType.VENDOR,
        wa_id=vendor_wa_id,
    )
    targets = settings.admin_wa_ids or {vendor_wa_id}
    text = _vendor_update_text(decision.intent, vendor_wa_id)
    return [OutboundMessage(target, text) for target in sorted(targets)]


def get_run_snapshot(db: Session, run_id: str) -> Run | None:
    return get_run_by_run_id(db, run_id)


def get_run_timeline(db: Session, run_id: str):
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return None
    return get_timeline(db, run)


def get_runs(db: Session, status: str | None = None) -> list[Run]:
    return list_runs(db, status=status)
