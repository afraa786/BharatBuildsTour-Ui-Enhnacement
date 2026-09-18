import pytest

from app.modules.runs import cart_flow
from app.modules.runs import service as runs_service
from app.modules.runs.models import BuyerCartSession
from app.modules.runs.state_machine import RunStatus
from app.modules.whatsapp.client import build_button_interactive, build_list_interactive


class FakeDb:
    def add(self, obj):
        pass

    def flush(self):
        pass


class FakeRun:
    def __init__(self, run_id: str, buyer_wa_id: str, raw_text: str):
        self.run_id = run_id
        self.buyer_wa_id = buyer_wa_id
        self.raw_text = raw_text
        self.status = RunStatus.RECEIVED.value
        self.version = 1
        self.line_items: list = []
        self.quote_snapshot: dict | None = None
        self.quote_id: str | None = None
        self.payment_id: str | None = None
        self.invoice_id: str | None = None


@pytest.fixture
def cart_env(monkeypatch):
    sessions: dict[str, BuyerCartSession] = {}
    created_runs: list[FakeRun] = []

    def _get_open_run(db, wa_id):
        return None

    def _get_cart_session(db, wa_id):
        return sessions.get(wa_id)

    def _get_or_create_cart_session(db, wa_id, phone_number_id, business_id=None):
        if wa_id not in sessions:
            sessions[wa_id] = BuyerCartSession(
                wa_id=wa_id,
                phone_number_id=phone_number_id,
                business_id=business_id,
                step="IDLE",
                cart=[],
            )
        return sessions[wa_id]

    def _create_run(db, buyer_wa_id, buyer_name, raw_text, business_id=None):
        run = FakeRun(f"RFQ-{len(created_runs) + 1}", buyer_wa_id, raw_text)
        run.business_id = business_id
        created_runs.append(run)
        return run

    monkeypatch.setattr(runs_service, "get_open_run_for_buyer", _get_open_run)
    monkeypatch.setattr(runs_service, "get_cart_session", _get_cart_session)
    monkeypatch.setattr(runs_service, "get_or_create_cart_session", _get_or_create_cart_session)
    monkeypatch.setattr(runs_service, "create_run", _create_run)
    monkeypatch.setattr(runs_service, "add_event", lambda *a, **k: None)
    monkeypatch.setattr(runs_service, "create_approval", lambda *a, **k: None)

    return sessions, created_runs


def test_catalogue_query_opens_guided_catalog(cart_env) -> None:
    sessions, _ = cart_env
    outbound = runs_service.process_buyer_message(
        db=FakeDb(), buyer_wa_id="buyer-1", text_body="what do you sell"
    )

    assert len(outbound) == 1
    assert outbound[0].message_type == "interactive"
    assert outbound[0].interactive["type"] == "list"
    assert sessions["buyer-1"].step == cart_flow.CartStep.BROWSING.value


def test_item_tap_prompts_for_quantity(cart_env) -> None:
    sessions, _ = cart_env
    sessions["buyer-1"] = BuyerCartSession(
        wa_id="buyer-1", phone_number_id=None, step=cart_flow.CartStep.BROWSING.value, cart=[]
    )

    outbound = runs_service.process_buyer_message(
        db=FakeDb(),
        buyer_wa_id="buyer-1",
        text_body="LED Bulb 9W",
        interactive_reply_id=cart_flow.item_reply_id("LED-9W"),
    )

    assert len(outbound) == 1
    assert "LED Bulb 9W" in outbound[0].text
    session = sessions["buyer-1"]
    assert session.step == cart_flow.CartStep.AWAITING_QTY.value
    assert session.pending_sku == "LED-9W"


def test_quantity_reply_adds_to_cart_and_shows_menu(cart_env) -> None:
    sessions, _ = cart_env
    sessions["buyer-1"] = BuyerCartSession(
        wa_id="buyer-1",
        phone_number_id=None,
        step=cart_flow.CartStep.AWAITING_QTY.value,
        pending_sku="LED-9W",
        cart=[],
    )

    outbound = runs_service.process_buyer_message(db=FakeDb(), buyer_wa_id="buyer-1", text_body="5")

    session = sessions["buyer-1"]
    assert session.step == cart_flow.CartStep.CART_MENU.value
    assert session.cart == [
        {"sku": "LED-9W", "name": "LED Bulb 9W", "unit": "pc", "unit_price": "95.00", "qty": 5}
    ]
    assert outbound[0].message_type == "interactive"
    assert outbound[0].interactive["type"] == "button"


def test_add_more_returns_to_browsing_with_cart_preserved(cart_env) -> None:
    sessions, _ = cart_env
    existing_cart = [
        {"sku": "LED-9W", "name": "LED Bulb 9W", "unit": "pc", "unit_price": "95.00", "qty": 5}
    ]
    sessions["buyer-1"] = BuyerCartSession(
        wa_id="buyer-1",
        phone_number_id=None,
        step=cart_flow.CartStep.CART_MENU.value,
        cart=existing_cart,
    )

    outbound = runs_service.process_buyer_message(
        db=FakeDb(),
        buyer_wa_id="buyer-1",
        text_body="Add more",
        interactive_reply_id=cart_flow.ACTION_ADD_MORE,
    )

    session = sessions["buyer-1"]
    assert session.step == cart_flow.CartStep.BROWSING.value
    assert session.cart == existing_cart
    assert outbound[0].interactive["type"] == "list"


def test_checkout_creates_run_through_existing_pipeline(cart_env) -> None:
    sessions, created_runs = cart_env
    sessions["buyer-1"] = BuyerCartSession(
        wa_id="buyer-1",
        phone_number_id=None,
        step=cart_flow.CartStep.CART_MENU.value,
        cart=[
            {"sku": "LED-9W", "name": "LED Bulb 9W", "unit": "pc", "unit_price": "95.00", "qty": 5}
        ],
    )

    outbound = runs_service.process_buyer_message(
        db=FakeDb(),
        buyer_wa_id="buyer-1",
        text_body="Checkout",
        interactive_reply_id=cart_flow.ACTION_CHECKOUT,
    )

    session = sessions["buyer-1"]
    assert session.step == cart_flow.CartStep.IDLE.value
    assert session.cart == []
    assert len(created_runs) == 1
    assert created_runs[0].line_items[0]["sku"] == "LED-9W"
    assert created_runs[0].status == RunStatus.QUOTE_SENT.value
    assert outbound[0].message_type == "interactive"
    assert outbound[0].interactive["type"] == "button"
    assert "LED Bulb 9W" in outbound[0].text


def test_interruption_mid_quantity_prompt_answers_then_resumes(cart_env, monkeypatch) -> None:
    sessions, _ = cart_env
    sessions["buyer-1"] = BuyerCartSession(
        wa_id="buyer-1",
        phone_number_id=None,
        step=cart_flow.CartStep.AWAITING_QTY.value,
        pending_sku="LED-9W",
        cart=[],
        last_prompt={
            "text": "How many pc of LED Bulb 9W would you like?",
            "message_type": "text",
            "interactive": None,
        },
    )
    monkeypatch.setattr(
        runs_service, "sales_desk_chat", lambda *a, **k: "We deliver across the city."
    )

    outbound = runs_service.process_buyer_message(
        db=FakeDb(), buyer_wa_id="buyer-1", text_body="do you deliver to Pune?"
    )

    assert len(outbound) == 2
    assert outbound[0].text == "We deliver across the city."
    assert "Back to your order:" in outbound[1].text
    assert "How many pc of LED Bulb 9W" in outbound[1].text
    session = sessions["buyer-1"]
    assert session.step == cart_flow.CartStep.AWAITING_QTY.value
    assert session.pending_sku == "LED-9W"
    assert session.cart == []


def test_accept_quote_via_button_id_bypasses_phrase_matching(monkeypatch) -> None:
    run = FakeRun("RFQ-9", "buyer-1", "5 pc LED Bulb 9W")
    run.status = RunStatus.QUOTE_SENT.value
    run.quote_snapshot = {"total": "560.00"}

    monkeypatch.setattr(runs_service, "get_open_run_for_buyer", lambda db, wa_id: run)
    monkeypatch.setattr(runs_service, "add_event", lambda *a, **k: None)

    outbound = runs_service.process_buyer_message(
        db=FakeDb(),
        buyer_wa_id="buyer-1",
        text_body="Accept quote",
        interactive_reply_id=cart_flow.QUOTE_ACTION_ACCEPT,
    )

    assert run.status == RunStatus.PAYMENT_PENDING.value
    assert "pay.stockaware.test" in outbound[0].text


def test_build_list_interactive_rejects_more_than_ten_rows() -> None:
    sections = [{"title": "All", "rows": [{"id": f"item:{i}", "title": str(i)} for i in range(11)]}]
    with pytest.raises(ValueError):
        build_list_interactive(body="b", button_text="View", sections=sections)


def test_build_button_interactive_rejects_more_than_three_buttons() -> None:
    with pytest.raises(ValueError):
        build_button_interactive(body="b", buttons=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")])
