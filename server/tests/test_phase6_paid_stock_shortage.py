"""Verified money remains paid, but post-link stock shortage blocks invoice."""

from sqlalchemy import update
from test_phase4_postgres import _event, _webhook
from test_phase4_postgres import payment_context as phase4_payment_context
from test_phase5_postgres import _invoice
from test_phase5_postgres import invoice_context as phase5_invoice_context

from app.modules.inventory.models import Inventory
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]
payment_context = phase4_payment_context
invoice_context = phase5_invoice_context


def test_paid_after_stock_shortage_is_held_not_discarded(invoice_context, pg_session):
    context = invoice_context
    pg_session.execute(
        update(Inventory)
        .where(
            Inventory.business_id == DEMO_BUSINESS_ID,
            Inventory.product_id == context["product_id"],
        )
        .values(on_hand_qty=0)
    )
    paid = _webhook(
        context["client"],
        _event(context["quote"].total_paise),
        event_id="evt_phase6_shortage",
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert paid.json()["reconciliation_hold"] is True
    blocked = _invoice(context)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PAYMENT_RECONCILIATION_REQUIRED"
