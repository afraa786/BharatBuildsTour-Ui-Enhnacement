from dataclasses import dataclass, field

from app.modules.runs import service
from app.modules.runs.service import process_admin_message
from app.modules.runs.state_machine import RunStatus


@dataclass
class FakeRun:
    run_id: str = "RFQ-1042"
    status: str = RunStatus.QUOTE_SENT.value
    buyer_wa_id: str = "buyer"
    quote_snapshot: dict = field(default_factory=lambda: {"total": "100.00", "items": []})
    payment_id: str | None = None
    invoice_id: str | None = None
    version: int = 1


def _patch_run_store(monkeypatch, run: FakeRun, events: list[tuple[str, dict | None]]):
    monkeypatch.setattr(service, "get_run_by_run_id", lambda db, run_id: run)
    monkeypatch.setattr(
        service,
        "add_event",
        lambda db, found_run, role, event, metadata=None: events.append((event, metadata)),
    )

    def fake_transition(db, found_run, target, role, event, metadata=None):
        found_run.status = target.value
        found_run.version += 1
        events.append((event, metadata))

    monkeypatch.setattr(service, "_transition", fake_transition)


def test_casual_yes_does_not_approve_anything() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="yes")
    assert len(outbound) == 1
    lowered = outbound[0].text.lower()
    assert "approved" not in lowered
    assert "rejected" not in lowered
    assert "rfq-" not in lowered


def test_casual_ok_prompts_for_exact_run_id() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="ok approve it")
    assert "exact RFQ ID" in outbound[0].text
    assert "Approve RFQ-1042" in outbound[0].text


def test_approve_requires_exact_command_syntax_and_returns_safe_prompt() -> None:
    outbound = process_admin_message(
        db=None, admin_wa_id="admin", text_body="please approve RFQ-1042 thanks"
    )
    assert "exact RFQ ID" in outbound[0].text
    assert "Approve RFQ-1042" in outbound[0].text


def test_exact_payment_link_command_is_deterministic_and_needs_store() -> None:
    outbound = process_admin_message(
        db=None, admin_wa_id="admin", text_body="Send payment link RFQ-1042"
    )
    assert len(outbound) == 1
    assert "live run store" in outbound[0].text


def test_exact_invoice_command_is_deterministic_and_needs_store() -> None:
    outbound = process_admin_message(
        db=None, admin_wa_id="admin", text_body="Send invoice RFQ-1042"
    )
    assert len(outbound) == 1
    assert "Invoice actions need" in outbound[0].text


def test_show_pending_payments_is_exact_read_command() -> None:
    outbound = process_admin_message(
        db=None, admin_wa_id="admin", text_body="Show pending payments"
    )
    assert outbound[0].text == "I need the live run store to show pending payments."


def test_show_low_stock_is_exact_read_command() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="Show low stock")
    assert outbound[0].text.startswith("Low stock:")


def test_send_payment_link_exact_command_transitions_and_sends(monkeypatch) -> None:
    run = FakeRun()
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    outbound = process_admin_message(
        db=object(), admin_wa_id="admin", text_body="Send payment link RFQ-1042"
    )

    assert run.status == RunStatus.PAYMENT_PENDING.value
    assert run.payment_id == "pay_1042"
    assert [message.to for message in outbound] == ["buyer", "admin"]
    assert outbound[-1].text == "Payment link sent for RFQ-1042."


def test_resend_payment_link_requires_existing_link(monkeypatch) -> None:
    run = FakeRun(status=RunStatus.QUOTE_SENT.value)
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    outbound = process_admin_message(
        db=object(), admin_wa_id="admin", text_body="Resend payment link RFQ-1042"
    )

    assert outbound[0].text == "RFQ-1042 has no payment link to resend yet."


def test_send_invoice_requires_verified_payment(monkeypatch) -> None:
    run = FakeRun(status=RunStatus.PAYMENT_PENDING.value)
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    outbound = process_admin_message(
        db=object(), admin_wa_id="admin", text_body="Send invoice RFQ-1042"
    )

    assert "Payment must be provider-verified first" in outbound[0].text


def test_send_invoice_exact_command_generates_after_verified_payment(monkeypatch) -> None:
    run = FakeRun(status=RunStatus.PAYMENT_CONFIRMED.value)
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    outbound = process_admin_message(
        db=object(), admin_wa_id="admin", text_body="Send invoice RFQ-1042"
    )

    assert run.status == RunStatus.INVOICE_GENERATED.value
    assert run.invoice_id == "INV-1042"
    assert [message.to for message in outbound] == ["buyer", "admin"]
    assert outbound[-1].text == "Invoice sent for RFQ-1042."


def test_resend_invoice_requires_existing_invoice(monkeypatch) -> None:
    run = FakeRun(status=RunStatus.PAYMENT_CONFIRMED.value)
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    outbound = process_admin_message(
        db=object(), admin_wa_id="admin", text_body="Resend invoice RFQ-1042"
    )

    assert outbound[0].text == "RFQ-1042 has no invoice to resend yet."


def test_ops_exact_commands_record_events(monkeypatch) -> None:
    run = FakeRun()
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    commands = [
        "Mark reminder done RFQ-1042",
        "Escalate RFQ-1042",
        "Pause RFQ-1042",
        "Close RFQ-1042",
        "Assign vendor RFQ-1042 Shakti Electricals",
        "Create reminder RFQ-1042 call tomorrow",
    ]
    for command in commands:
        outbound = process_admin_message(db=object(), admin_wa_id="admin", text_body=command)
        assert outbound[0].text.startswith("Noted for RFQ-1042")

    event_names = [event for event, metadata in events]
    assert event_names == [
        "Reminder marked done",
        "Escalated by admin command",
        "Pause requested",
        "Close requested",
        "Vendor assigned",
        "Reminder created",
    ]
    assert events[-2][1]["vendor"] == "Shakti Electricals"
    assert events[-1][1]["reminder"] == "call tomorrow"


def test_assign_vendor_exact_command_requires_vendor(monkeypatch) -> None:
    run = FakeRun()
    events: list[tuple[str, dict | None]] = []
    _patch_run_store(monkeypatch, run, events)

    outbound = process_admin_message(
        db=object(), admin_wa_id="admin", text_body="Assign vendor RFQ-1042"
    )

    assert outbound[0].text == "Tell me which vendor to assign for RFQ-1042."
    assert events == []
