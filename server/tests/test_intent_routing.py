import pytest

from app.modules.runs import service as runs_service
from app.modules.runs.intent_router import ActorType, IntentType, route_message
from app.modules.runs.service import process_admin_message, process_vendor_message
from app.modules.runs.state_machine import RunStatus


def test_admin_summary_message_routes_to_important_updates_intent() -> None:
    decision = route_message(
        text="what all stuck?",
        actor_hint=ActorType.ADMIN,
    )
    assert decision.actor is ActorType.ADMIN
    assert decision.intent is IntentType.IMPORTANT_UPDATES


def test_quote_sent_buyer_message_treats_send_link_as_acceptance() -> None:
    decision = route_message(
        text="okay send link",
        actor_hint=ActorType.BUYER,
        current_status=RunStatus.QUOTE_SENT.value,
    )
    assert decision.actor is ActorType.BUYER
    assert decision.intent is IntentType.ACCEPT_QUOTE


def test_payment_done_is_a_claim_not_a_confirmation() -> None:
    decision = route_message(
        text="payment done",
        actor_hint=ActorType.BUYER,
        current_status=RunStatus.PAYMENT_PENDING.value,
    )
    assert decision.intent is IntentType.PAYMENT_CLAIM


def test_vendor_price_revision_is_detected_from_natural_language() -> None:
    decision = route_message(text="new price list from monday")
    assert decision.actor is ActorType.VENDOR
    assert decision.intent is IntentType.VENDOR_PRICE_REVISION


def test_baker_style_order_still_routes_as_buyer_request() -> None:
    decision = route_message(text="Need 2kg kaju katli for Sunday pickup")
    assert decision.actor is ActorType.BUYER
    assert decision.intent is IntentType.REQUEST_ORDER


def test_fuzzy_admin_approval_needs_exact_run_id() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="approve it")
    assert len(outbound) == 1
    assert "exact RFQ ID" in outbound[0].text
    assert "Approve RFQ-1042" in outbound[0].text


def test_vendor_message_turns_into_admin_alert() -> None:
    outbound = process_vendor_message(
        db=None,
        vendor_wa_id="vendor-1",
        text_body="dispatch delayed by 2 days",
    )
    assert len(outbound) == 1
    assert "Vendor update" in outbound[0].text
    assert "delay" in outbound[0].text.lower()


def test_hinglish_negotiation_routes_correctly() -> None:
    decision = route_message(text="bhai thoda kam karo")
    assert decision.actor is ActorType.BUYER
    assert decision.intent is IntentType.NEGOTIATE_PRICE


def test_hindi_invoice_request_routes_correctly() -> None:
    decision = route_message(
        text="इनवॉइस भेज दो",
        actor_hint=ActorType.BUYER,
        current_status=RunStatus.PAYMENT_CONFIRMED.value,
    )
    assert decision.intent is IntentType.REQUEST_INVOICE


def test_marathi_admin_pending_updates_route_correctly() -> None:
    decision = route_message(
        text="आज काय pending आहे?",
        actor_hint=ActorType.ADMIN,
    )
    assert decision.actor is ActorType.ADMIN
    assert decision.intent is IntentType.IMPORTANT_UPDATES


def test_tamil_order_request_routes_correctly() -> None:
    decision = route_message(text="நாளைக்கு 20 பீஸ் வேண்டும்")
    assert decision.actor is ActorType.BUYER
    assert decision.intent is IntentType.REQUEST_ORDER


def test_telugu_payment_link_request_routes_correctly() -> None:
    decision = route_message(
        text="payment link మళ్లీ పంపండి",
        actor_hint=ActorType.BUYER,
        current_status=RunStatus.PAYMENT_PENDING.value,
    )
    assert decision.intent is IntentType.REQUEST_PAYMENT_LINK


def test_bengali_quote_request_routes_correctly() -> None:
    decision = route_message(text="কালকের জন্য 20 পিস চাই")
    assert decision.actor is ActorType.BUYER
    assert decision.intent is IntentType.REQUEST_ORDER


def test_kannada_admin_pending_payments_route_correctly() -> None:
    decision = route_message(
        text="payment ಬಂದಿದೆಯಾ?",
        actor_hint=ActorType.ADMIN,
    )
    assert decision.actor is ActorType.ADMIN
    assert decision.intent is IntentType.SHOW_PENDING_PAYMENTS


@pytest.mark.parametrize(
    ("text", "actor_hint", "status", "expected_intent"),
    [
        (
            "okay send link",
            ActorType.BUYER,
            RunStatus.QUOTE_SENT.value,
            IntentType.ACCEPT_QUOTE,
        ),
        (
            "payment link send karo",
            ActorType.BUYER,
            RunStatus.QUOTE_SENT.value,
            IntentType.ACCEPT_QUOTE,
        ),
        (
            "पेमेंट कर दिया",
            ActorType.BUYER,
            RunStatus.PAYMENT_PENDING.value,
            IntentType.PAYMENT_CLAIM,
        ),
        (
            "पेमेंट कर दिया",
            ActorType.BUYER,
            RunStatus.QUOTE_SENT.value,
            IntentType.UNKNOWN,
        ),
        (
            "GST invoice PDF भेज दीजिए",
            ActorType.BUYER,
            RunStatus.PAYMENT_CONFIRMED.value,
            IntentType.REQUEST_INVOICE,
        ),
        (
            "पेमेंट लिंक पुन्हा पाठवा",
            ActorType.BUYER,
            RunStatus.PAYMENT_PENDING.value,
            IntentType.REQUEST_PAYMENT_LINK,
        ),
        (
            "இன்று என்ன என்ன pending இருக்கு?",
            ActorType.ADMIN,
            None,
            IntentType.IMPORTANT_UPDATES,
        ),
        (
            "Low stock items ತೋರಿಸಿ",
            ActorType.ADMIN,
            None,
            IntentType.SHOW_LOW_STOCK,
        ),
    ],
)
def test_multilingual_routing_matrix(
    text: str,
    actor_hint: ActorType,
    status: str | None,
    expected_intent: IntentType,
) -> None:
    decision = route_message(
        text=text,
        actor_hint=actor_hint,
        current_status=status,
    )
    assert decision.intent is expected_intent


def test_trusted_vendor_wa_id_beats_lexical_fallback() -> None:
    decision = route_message(
        text="Need stock available next week for 20 pcs",
        wa_id="vendor-42",
        vendor_wa_ids={"vendor-42"},
    )
    assert decision.actor is ActorType.VENDOR
    assert decision.actor_source == "trusted_vendor"


def test_buyer_stock_question_does_not_become_vendor_update() -> None:
    decision = route_message(
        text="stock available next week for 20 pcs?",
        actor_hint=ActorType.BUYER,
    )
    assert decision.actor is ActorType.BUYER
    assert decision.intent is IntentType.REQUEST_ORDER


def test_greeting_and_catalogue_question_do_not_route_as_order() -> None:
    greeting = route_message(text="hiii", actor_hint=ActorType.BUYER)
    catalogue = route_message(text="what do you sell", actor_hint=ActorType.BUYER)

    assert greeting.intent is IntentType.GREETING
    assert catalogue.intent is IntentType.CATALOGUE_QUERY


def test_catalogue_question_does_not_become_clarification_reply() -> None:
    decision = route_message(
        text="what do you sell",
        actor_hint=ActorType.BUYER,
        current_status=RunStatus.WAITING_FOR_CLARIFICATION.value,
    )

    assert decision.intent is IntentType.CATALOGUE_QUERY


def test_new_buyer_greeting_does_not_create_rfq_run(monkeypatch) -> None:
    created = False

    def _create_run(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal created
        created = True
        raise AssertionError("greeting should not create a run")

    monkeypatch.setattr(runs_service, "get_open_run_for_buyer", lambda *args, **kwargs: None)
    monkeypatch.setattr(runs_service, "create_run", _create_run)

    outbound = runs_service.process_buyer_message(db=None, buyer_wa_id="buyer", text_body="hiii")

    assert created is False
    assert len(outbound) == 1
    assert "item name and quantity" in outbound[0].text
