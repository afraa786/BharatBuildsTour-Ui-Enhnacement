"""Demo-safe quote-to-cash workflow endpoints.

This router gives the UI and integration team a working, deterministic MVP before
the PostgreSQL commercial modules are connected.  It deliberately does not claim
to verify real payment-provider events: ``/demo/payments/{id}/confirm`` is only a
local demo action and is clearly labelled in its response.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/demo", tags=["demo-workflow"])


class RfqLine(BaseModel):
    requested_name: str = Field(min_length=2, max_length=120)
    quantity: int = Field(gt=0, le=10_000)
    unit: Literal["each", "metre"]


class WhatsAppIntake(BaseModel):
    source_message_id: str = Field(min_length=4, max_length=128)
    buyer_name: str = Field(min_length=2, max_length=120)
    buyer_phone: str = Field(min_length=8, max_length=24)
    lines: list[RfqLine] = Field(min_length=1, max_length=20)


class AdminCommand(BaseModel):
    command: str = Field(min_length=2, max_length=240)


CATALOG = [
    {"sku": "MCB-32A-SP", "name": "32A SP MCB C Curve", "unit": "each", "price_paise": 26000, "stock": 38, "threshold": 12, "aliases": ["32 amp mcb", "32a mcb", "single pole 32a mcb"]},
    {"sku": "WIRE-1.5SQ-RED", "name": "1.5 sq mm FR Copper Wire Red", "unit": "metre", "price_paise": 2050, "stock": 450, "threshold": 180, "aliases": ["1.5 sq red wire", "1.5mm red wire", "red wire 1.5 sq"]},
    {"sku": "LED-9W", "name": "9W LED Bulb Cool Day Light", "unit": "each", "price_paise": 7500, "stock": 20, "threshold": 30, "aliases": ["9w bulb", "9 watt led bulb", "9w led"]},
    {"sku": "LED-12W", "name": "12W LED Bulb Cool Day Light", "unit": "each", "price_paise": 9300, "stock": 80, "threshold": 30, "aliases": ["12w bulb", "12 watt led bulb", "12w led"]},
]


class DemoStore:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.message_runs: dict[str, str] = {}
        self.payments: dict[str, dict] = {}
        self.invoices: dict[str, dict] = {}

    @staticmethod
    def event(event_type: str, message: str) -> dict:
        return {"id": f"EVT-{uuid4().hex[:8].upper()}", "type": event_type, "message": message, "occurred_at": datetime.now(UTC).isoformat()}

    def match(self, line: RfqLine) -> dict | None:
        needle = line.requested_name.lower().strip()
        for product in CATALOG:
            if needle in product["name"].lower() or any(alias in needle or needle in alias for alias in product["aliases"]):
                return product
        return None


store = DemoStore()


def public_run(run: dict) -> dict:
    return {key: value for key, value in run.items() if key != "timeline"}


@router.get("/products")
def products() -> list[dict]:
    return [{key: value for key, value in product.items() if key != "aliases"} for product in CATALOG]


@router.post("/webhook/whatsapp", status_code=status.HTTP_201_CREATED)
def whatsapp_intake(payload: WhatsAppIntake) -> dict:
    existing = store.message_runs.get(payload.source_message_id)
    if existing:
        return {"duplicate": True, "run": public_run(store.runs[existing])}

    lines: list[dict] = []
    needs_clarification = False
    for requested in payload.lines:
        product = store.match(requested)
        if product is None:
            lines.append({**requested.model_dump(), "match_status": "NOT_FOUND"})
            needs_clarification = True
            continue
        available = min(requested.quantity, product["stock"])
        lines.append({**requested.model_dump(), "match_status": "MATCHED", "sku": product["sku"], "product_name": product["name"], "available_quantity": available, "stock_status": "AVAILABLE" if requested.quantity <= product["stock"] else "INSUFFICIENT", "unit_price_paise": product["price_paise"], "line_total_paise": requested.quantity * product["price_paise"]})
    run_id = f"RUN-{uuid4().hex[:8].upper()}"
    state = "NEEDS_CLARIFICATION" if needs_clarification else "QUOTED"
    total = sum(line.get("line_total_paise", 0) for line in lines)
    run = {"id": run_id, "buyer_name": payload.buyer_name, "buyer_phone": payload.buyer_phone, "status": state, "lines": lines, "quote": {"id": f"QT-{uuid4().hex[:6].upper()}", "version": 1, "status": "DRAFT" if needs_clarification else "SENT", "total_paise": total, "currency": "INR", "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat()}, "timeline": []}
    run["timeline"].append(store.event("RFQ_RECEIVED", f"RFQ received from {payload.buyer_name}."))
    run["timeline"].append(store.event("QUOTE_READY" if not needs_clarification else "CLARIFICATION_REQUIRED", "Quote prepared." if not needs_clarification else "A product could not be matched."))
    store.runs[run_id] = run
    store.message_runs[payload.source_message_id] = run_id
    return {"duplicate": False, "run": public_run(run), "next_message": "Please share the brand, poles and product photo or SKU." if needs_clarification else "Your quote is ready. Reply ACCEPT to proceed."}


@router.get("/runs")
def runs() -> list[dict]:
    return [public_run(run) for run in reversed(list(store.runs.values()))]


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = store.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return public_run(run)


@router.get("/runs/{run_id}/timeline")
def timeline(run_id: str) -> list[dict]:
    run = store.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run["timeline"]


@router.post("/runs/{run_id}/accept")
def accept_quote(run_id: str) -> dict:
    run = store.runs.get(run_id)
    if not run or run["status"] != "QUOTED":
        raise HTTPException(status_code=409, detail="only a sent quote can be accepted")
    run["status"] = "ACCEPTED"
    run["quote"]["status"] = "ACCEPTED"
    run["timeline"].append(store.event("QUOTE_ACCEPTED", "Buyer accepted the saved quote version."))
    return public_run(run)


@router.post("/payments/create-link")
def create_payment_link(payload: dict) -> dict:
    run_id = str(payload.get("run_id", ""))
    run = store.runs.get(run_id)
    if not run or run["status"] != "ACCEPTED":
        raise HTTPException(status_code=409, detail="an accepted quote is required")
    for payment in store.payments.values():
        if payment["run_id"] == run_id:
            return payment
    payment_id = f"PAY-{uuid4().hex[:8].upper()}"
    payment = {"id": payment_id, "run_id": run_id, "quote_id": run["quote"]["id"], "status": "PENDING", "amount_paise": run["quote"]["total_paise"], "currency": "INR", "url": f"https://pay.stockaware.demo/{payment_id}", "demo_mode": True}
    store.payments[payment_id] = payment
    run["status"] = "PAYMENT_PENDING"
    run["timeline"].append(store.event("PAYMENT_LINK_CREATED", "Demo payment link created."))
    return payment


@router.get("/payments/{payment_id}")
def get_payment(payment_id: str) -> dict:
    payment = store.payments.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="payment not found")
    return payment


@router.post("/demo/payments/{payment_id}/confirm")
def confirm_demo_payment(payment_id: str) -> dict:
    payment = store.payments.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="payment not found")
    if payment["status"] == "PAID":
        return {**payment, "idempotent": True}
    payment["status"] = "PAID"
    run = store.runs[payment["run_id"]]
    run["status"] = "PAID"
    run["timeline"].append(store.event("PAYMENT_CONFIRMED", "Demo payment confirmed; production requires a verified provider webhook."))
    return {**payment, "idempotent": False}


@router.post("/invoice/generate")
def generate_invoice(payload: dict) -> dict:
    payment_id = str(payload.get("payment_id", ""))
    payment = store.payments.get(payment_id)
    if not payment or payment["status"] != "PAID":
        raise HTTPException(status_code=409, detail="a confirmed payment is required")
    if payment_id in store.invoices:
        return {**store.invoices[payment_id], "idempotent": True}
    invoice = {"id": f"INV-{uuid4().hex[:8].upper()}", "number": f"SA/2026/{len(store.invoices) + 1:04d}", "payment_id": payment_id, "quote_id": payment["quote_id"], "total_paise": payment["amount_paise"], "currency": "INR", "artifact_url": f"/demo/invoices/{payment_id}.pdf"}
    store.invoices[payment_id] = invoice
    run = store.runs[payment["run_id"]]
    run["status"] = "INVOICED"
    run["timeline"].append(store.event("INVOICE_GENERATED", f"Invoice {invoice['number']} generated."))
    return {**invoice, "idempotent": False}


@router.post("/admin/command")
def admin_command(payload: AdminCommand) -> dict:
    command = payload.command.strip().lower()
    if command == "show low stock":
        return {"result_type": "LOW_STOCK", "items": [product for product in CATALOG if product["stock"] <= product["threshold"]]}
    if command == "show vendor updates":
        return {"result_type": "VENDOR_UPDATE", "message": "Lumina Electricals revised LED prices effective 20 September. Review open quotes."}
    if command == "show pending payments":
        return {"result_type": "PAYMENTS", "items": [payment for payment in store.payments.values() if payment["status"] == "PENDING"]}
    return {"result_type": "HELP", "message": "Try: show low stock, show vendor updates, or show pending payments."}
