"""Previously issued invoice remains replayable after a later reconciliation hold."""

from sqlalchemy import select
from test_phase4_postgres import payment_context as phase4_payment_context
from test_phase5_postgres import _invoice, _pay
from test_phase5_postgres import invoice_context as phase5_invoice_context

from app.modules.payments.models import Payment

pytest_plugins = ["test_phase1_postgres"]
payment_context = phase4_payment_context
invoice_context = phase5_invoice_context


def test_issued_invoice_replay_survives_later_payment_hold(invoice_context, pg_session):
    context = invoice_context
    _pay(context)
    issued = _invoice(context)
    assert issued.status_code == 200
    payment = pg_session.scalar(select(Payment).where(Payment.id == context["payment_id"]))
    payment.reconciliation_hold = True
    assert _invoice(context).json() == issued.json()
    assert _invoice(context, key="later-retry").json() == issued.json()
