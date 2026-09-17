import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.runs import mock_desks
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
_ACCEPT_WORDS = {"accept", "accepted", "confirm", "confirmed", "ok", "okay"}

HELP_TEXT = (
    "Sorry, I didn't recognize that command. Try: Approve RFQ-1042, "
    "Reject RFQ-1042, Show RFQ-1042, Why was RFQ-1042 blocked?, "
    "Show open quotes today"
)


@dataclass
class OutboundMessage:
    to: str
    text: str


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


def process_buyer_message(db: Session, buyer_wa_id: str, text_body: str) -> list[OutboundMessage]:
    run = get_open_run_for_buyer(db, buyer_wa_id)

    if run is None:
        run = create_run(db, buyer_wa_id, buyer_name=None, raw_text=text_body)
        add_event(db, run, "Manager", "Run received from WhatsApp", {"text": text_body})
        _transition(db, run, RunStatus.NORMALIZING, "Manager", "Normalizing buyer request")
        return _run_pipeline(db, run, text_body)

    current = RunStatus(run.status)

    if current == RunStatus.WAITING_FOR_CLARIFICATION:
        run.raw_text = f"{run.raw_text} {text_body}"
        _transition(db, run, RunStatus.NORMALIZING, "Manager", "Received clarification")
        return _run_pipeline(db, run, run.raw_text)

    if current == RunStatus.QUOTE_SENT:
        if text_body.strip().lower() in _ACCEPT_WORDS:
            _transition(db, run, RunStatus.ACCEPTED, "Sales Desk", "Buyer accepted quote")
            _transition(
                db, run, RunStatus.PAYMENT_LINK_SENT, "Accounts Desk", "Payment link created (mock)"
            )
            run.payment_id = f"pay_{run.run_id.split('-')[1]}"
            total = run.quote_snapshot["total"] if run.quote_snapshot else "0.00"
            link = f"https://pay.stockaware.test/{run.payment_id}"
            return [
                OutboundMessage(
                    buyer_wa_id, f"Complete payment here (mock link): {link} for ₹{total}"
                )
            ]
        run.raw_text = f"{run.raw_text} {text_body}"
        _transition(
            db,
            run,
            RunStatus.CHANGE_REQUESTED,
            "Sales Desk",
            "Buyer requested change",
            {"text": text_body},
        )
        _transition(
            db, run, RunStatus.NORMALIZING, "Manager", "Re-normalizing after change request"
        )
        return _run_pipeline(db, run, run.raw_text)

    add_event(
        db,
        run,
        "Manager",
        "Received message in non-actionable state",
        {"text": text_body, "status": current.value},
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


def _show_run_text(db: Session, run_id: str) -> str:
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return f"{run_id} not found."
    total = run.quote_snapshot["total"] if run.quote_snapshot else "-"
    return f"{run.run_id} — status: {run.status}\nBuyer: {run.buyer_wa_id}\nTotal: ₹{total}"


def _why_blocked_text(db: Session, run_id: str) -> str:
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


def _open_quotes_today_text(db: Session) -> str:
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


def process_admin_message(db: Session, admin_wa_id: str, text_body: str) -> list[OutboundMessage]:
    stripped = text_body.strip()

    if m := _APPROVE_RE.match(stripped):
        return approve_run(db, m.group(1).upper(), actor=admin_wa_id)
    if m := _REJECT_RE.match(stripped):
        return reject_run(db, m.group(1).upper(), actor=admin_wa_id)
    if m := _SHOW_RE.match(stripped):
        return [OutboundMessage(admin_wa_id, _show_run_text(db, m.group(1).upper()))]
    if m := _WHY_RE.match(stripped):
        return [OutboundMessage(admin_wa_id, _why_blocked_text(db, m.group(1).upper()))]
    if _OPEN_QUOTES_RE.match(stripped):
        return [OutboundMessage(admin_wa_id, _open_quotes_today_text(db))]

    return [OutboundMessage(admin_wa_id, HELP_TEXT)]


def get_run_snapshot(db: Session, run_id: str) -> Run | None:
    return get_run_by_run_id(db, run_id)


def get_run_timeline(db: Session, run_id: str):
    run = get_run_by_run_id(db, run_id)
    if run is None:
        return None
    return get_timeline(db, run)


def get_runs(db: Session, status: str | None = None) -> list[Run]:
    return list_runs(db, status=status)
