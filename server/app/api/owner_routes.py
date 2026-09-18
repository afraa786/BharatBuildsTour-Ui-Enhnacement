"""Business-scoped owner dashboard endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.owner_auth import CurrentUser
from app.db.session import get_db
from app.modules.catalog.models import Product
from app.modules.catalog.normalization import normalize_catalog_text
from app.modules.identity.models import Buyer
from app.modules.identity.owner_models import Category
from app.modules.inventory.models import Inventory
from app.modules.invoices.models import Invoice
from app.modules.payments.models import Payment
from app.modules.pricing.models import Quote
from app.modules.runs.models import Run
from app.modules.runs.service import get_agentcraft_events

router = APIRouter(tags=["owner-dashboard"])
Db = Annotated[Session, Depends(get_db)]


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProductIn(BaseModel):
    sku: str
    name: str
    category_id: UUID | None = None
    cost_unit_paise: int = Field(ge=0)
    base_unit_price_paise: int = Field(gt=0)
    gst_rate_bps: int = Field(ge=0, le=10000)
    stock_qty: Decimal = Field(default=0, ge=0)
    sellable_unit: str = "piece"
    stock_unit: str = "piece"
    pack_size: Decimal = Field(default=1, gt=0)


class ProductPatch(BaseModel):
    sku: str | None = None
    name: str | None = None
    category_id: UUID | None = None
    cost_unit_paise: int | None = Field(default=None, ge=0)
    base_unit_price_paise: int | None = Field(default=None, gt=0)
    gst_rate_bps: int | None = Field(default=None, ge=0, le=10000)
    stock_qty: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None


class BuyerIn(BaseModel):
    display_name: str
    whatsapp_e164: str | None = None
    is_customer: bool = False
    source: str | None = None
    legal_name: str | None = None
    billing_address: str | None = None
    gstin: str | None = None


class BuyerPatch(BaseModel):
    display_name: str | None = None
    is_customer: bool | None = None
    source: str | None = None
    last_contacted_at: datetime | None = None
    legal_name: str | None = None
    billing_address: str | None = None
    gstin: str | None = None


class StatusIn(BaseModel):
    status: str


class DeliveryIn(BaseModel):
    expected_delivery_date: datetime | None


def one(db, model, id, bid):
    row = db.scalar(select(model).where(model.id == id, model.business_id == bid))
    if not row:
        raise HTTPException(404, "Not found")
    return row


def product_out(db, p):
    stock = db.get(Inventory, {"business_id": p.business_id, "product_id": p.id})
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "category_id": p.category_id,
        "cost_unit_paise": p.cost_unit_paise,
        "base_unit_price_paise": p.base_unit_price_paise,
        "gst_rate_bps": p.gst_rate_bps,
        "stock_qty": stock.on_hand_qty if stock else 0,
        "active": p.active,
        "sellable_unit": p.sellable_unit,
        "stock_unit": p.stock_unit,
        "pack_size": p.pack_size,
    }


def buyer_out(b):
    return {
        k: getattr(b, k)
        for k in (
            "id",
            "display_name",
            "whatsapp_e164",
            "legal_name",
            "billing_address",
            "gstin",
            "is_customer",
            "source",
            "last_contacted_at",
            "created_at",
        )
    }


@router.get("/dashboard/summary")
def summary(db: Db, user: CurrentUser):
    b = user.business_id
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
            Payment.business_id == b, Payment.status == "PAID"
        )
    )
    statuses = dict(
        db.execute(
            select(Run.status, func.count()).where(Run.business_id == b).group_by(Run.status)
        ).all()
    )
    leads = (
        db.scalar(
            select(func.count())
            .select_from(Buyer)
            .where(Buyer.business_id == b, Buyer.is_customer.is_(False))
        )
        or 0
    )
    customers = (
        db.scalar(
            select(func.count())
            .select_from(Buyer)
            .where(Buyer.business_id == b, Buyer.is_customer.is_(True))
        )
        or 0
    )
    upcoming = db.scalars(
        select(Run)
        .where(
            Run.business_id == b,
            Run.expected_delivery_date.is_not(None),
            Run.status.not_in(("cancelled", "delivered")),
        )
        .order_by(Run.expected_delivery_date)
        .limit(10)
    )
    return {
        "total_sales_paise": paid,
        "runs_count_by_status": statuses,
        "leads_count": leads,
        "customers_count": customers,
        "upcoming_deliveries": [
            {
                "run_id": r.run_id,
                "buyer_name": r.buyer_name,
                "expected_delivery_date": r.expected_delivery_date,
            }
            for r in upcoming
        ],
    }


@router.get("/categories")
def list_categories(db: Db, user: CurrentUser):
    return [
        {"id": c.id, "name": c.name, "created_at": c.created_at}
        for c in db.scalars(
            select(Category).where(Category.business_id == user.business_id).order_by(Category.name)
        )
    ]


@router.post("/categories", status_code=201)
def add_category(body: CategoryIn, db: Db, user: CurrentUser):
    c = Category(business_id=user.business_id, name=body.name.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name, "created_at": c.created_at}


@router.patch("/categories/{id}")
def edit_category(id: UUID, body: CategoryIn, db: Db, user: CurrentUser):
    c = one(db, Category, id, user.business_id)
    c.name = body.name.strip()
    db.commit()
    return {"id": c.id, "name": c.name, "created_at": c.created_at}


@router.delete("/categories/{id}", status_code=204)
def delete_category(id: UUID, db: Db, user: CurrentUser):
    db.delete(one(db, Category, id, user.business_id))
    db.commit()
    return Response(status_code=204)


@router.get("/products")
def products(db: Db, user: CurrentUser, category_id: UUID | None = None):
    q = select(Product).where(Product.business_id == user.business_id)
    if category_id:
        q = q.where(Product.category_id == category_id)
    return [product_out(db, p) for p in db.scalars(q.order_by(Product.name))]


@router.post("/products", status_code=201)
def add_product(body: ProductIn, db: Db, user: CurrentUser):
    if body.category_id:
        one(db, Category, body.category_id, user.business_id)
    p = Product(
        business_id=user.business_id,
        sku=body.sku,
        normalized_sku=normalize_catalog_text(body.sku),
        name=body.name,
        normalized_name=normalize_catalog_text(body.name),
        category_id=body.category_id,
        cost_unit_paise=body.cost_unit_paise,
        base_unit_price_paise=body.base_unit_price_paise,
        gst_rate_bps=body.gst_rate_bps,
        sellable_unit=body.sellable_unit,
        stock_unit=body.stock_unit,
        pack_size=body.pack_size,
        indivisible=True,
        active=True,
    )
    db.add(p)
    db.flush()
    db.add(
        Inventory(
            business_id=user.business_id, product_id=p.id, on_hand_qty=body.stock_qty, version=1
        )
    )
    db.commit()
    return product_out(db, p)


@router.patch("/products/{id}")
def edit_product(id: UUID, body: ProductPatch, db: Db, user: CurrentUser):
    p = one(db, Product, id, user.business_id)
    v = body.model_dump(exclude_unset=True)
    stock = v.pop("stock_qty", None)
    if v.get("category_id"):
        one(db, Category, v["category_id"], user.business_id)
    for k, x in v.items():
        setattr(p, k, x)
    if "sku" in v:
        p.normalized_sku = normalize_catalog_text(p.sku)
    if "name" in v:
        p.normalized_name = normalize_catalog_text(p.name)
    if stock is not None:
        db.get(Inventory, {"business_id": user.business_id, "product_id": p.id}).on_hand_qty = stock
    db.commit()
    return product_out(db, p)


@router.delete("/products/{id}", status_code=204)
def delete_product(id: UUID, db: Db, user: CurrentUser):
    p = one(db, Product, id, user.business_id)
    p.active = False
    db.commit()
    return Response(status_code=204)


@router.get("/buyers")
def buyers(db: Db, user: CurrentUser, is_customer: bool | None = Query(default=None)):
    q = select(Buyer).where(Buyer.business_id == user.business_id)
    if is_customer is not None:
        q = q.where(Buyer.is_customer.is_(is_customer))
    return [buyer_out(x) for x in db.scalars(q.order_by(Buyer.display_name))]


@router.post("/buyers", status_code=201)
def add_buyer(body: BuyerIn, db: Db, user: CurrentUser):
    b = Buyer(business_id=user.business_id, **body.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    return buyer_out(b)


@router.patch("/buyers/{id}")
def edit_buyer(id: UUID, body: BuyerPatch, db: Db, user: CurrentUser):
    b = one(db, Buyer, id, user.business_id)
    v = body.model_dump(exclude_unset=True)
    for k, x in v.items():
        setattr(b, k, x)
    db.commit()
    return buyer_out(b)


def _row_id(value: str | None) -> UUID | None:
    """Run.quote_id/payment_id/invoice_id may hold mock-pipeline string ids
    (e.g. "Q-1005-V1") rather than real commercial-schema UUIDs; treat those
    as "no linked record" instead of erroring the whole run list."""
    if not value:
        return None
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def _quote_for_run(db, business_id, run) -> Quote | None:
    quote_id = _row_id(run.quote_id)
    if quote_id is not None:
        return db.scalar(
            select(Quote).where(Quote.business_id == business_id, Quote.id == quote_id)
        )
    if not run.quote_id:
        return None
    return db.scalar(
        select(Quote)
        .where(Quote.business_id == business_id, Quote.run_id == run.run_id)
        .order_by(Quote.quote_version.desc())
    )


def _payment_for_run(db, business_id, run) -> Payment | None:
    payment_id = _row_id(run.payment_id)
    if payment_id is not None:
        return db.scalar(
            select(Payment).where(Payment.business_id == business_id, Payment.id == payment_id)
        )
    if not run.payment_id:
        return None
    return db.scalar(
        select(Payment).where(Payment.business_id == business_id, Payment.run_id == run.run_id)
    )


def _invoice_for_run(db, business_id, run) -> Invoice | None:
    invoice_id = _row_id(run.invoice_id)
    if invoice_id is not None:
        return db.scalar(
            select(Invoice).where(Invoice.business_id == business_id, Invoice.id == invoice_id)
        )
    if not run.invoice_id:
        return None
    return db.scalar(
        select(Invoice).where(Invoice.business_id == business_id, Invoice.run_id == run.run_id)
    )


def run_out(db, r, b):
    q = _quote_for_run(db, b, r)
    p = _payment_for_run(db, b, r)
    i = _invoice_for_run(db, b, r)
    return {
        "id": r.id,
        "run_id": r.run_id,
        "status": r.status,
        "buyer_name": r.buyer_name,
        "buyer_wa_id": r.buyer_wa_id,
        "line_items": r.line_items,
        "quote_snapshot": r.quote_snapshot,
        "expected_delivery_date": r.expected_delivery_date,
        "created_at": r.created_at,
        "quote": {"id": q.id, "status": q.status, "total_paise": q.total_paise} if q else None,
        "payment": {
            "id": p.id,
            "status": p.status,
            "amount_paise": p.amount_paise,
            "paid_at": p.paid_at,
        }
        if p
        else None,
        "invoice": {
            "id": i.id,
            "invoice_number": i.invoice_number,
            "status": i.status,
            "total_paise": i.total_paise,
        }
        if i
        else None,
    }


@router.get("/runs")
def runs(db: Db, user: CurrentUser, status: str | None = None):
    q = select(Run).where(Run.business_id == user.business_id)
    if status:
        q = q.where(Run.status == status)
    return [run_out(db, r, user.business_id) for r in db.scalars(q.order_by(Run.created_at.desc()))]


@router.get("/runs/{run_id}")
def run(run_id: str, db: Db, user: CurrentUser):
    r = db.scalar(select(Run).where(Run.run_id == run_id, Run.business_id == user.business_id))
    if not r:
        raise HTTPException(404, "Not found")
    return run_out(db, r, user.business_id)


@router.get("/runs/{run_id}/agent-events")
def run_agent_events(run_id: str, db: Db, user: CurrentUser):
    events = get_agentcraft_events(db, run_id, business_id=user.business_id)
    if events is None:
        raise HTTPException(404, "Not found")
    return events


@router.patch("/runs/{run_id}/status")
def run_status(run_id: str, body: StatusIn, db: Db, user: CurrentUser):
    r = db.scalar(select(Run).where(Run.run_id == run_id, Run.business_id == user.business_id))
    if not r:
        raise HTTPException(404, "Not found")
    r.status = body.status
    db.commit()
    return run_out(db, r, user.business_id)


@router.patch("/runs/{run_id}/delivery-date")
def run_delivery(run_id: str, body: DeliveryIn, db: Db, user: CurrentUser):
    r = db.scalar(select(Run).where(Run.run_id == run_id, Run.business_id == user.business_id))
    if not r:
        raise HTTPException(404, "Not found")
    r.expected_delivery_date = body.expected_delivery_date
    db.commit()
    return run_out(db, r, user.business_id)


@router.get("/invoices")
def invoices(db: Db, user: CurrentUser):
    return [
        {
            "id": i.id,
            "invoice_number": i.invoice_number,
            "run_id": i.run_id,
            "status": i.status,
            "total_paise": i.total_paise,
            "issued_at": i.issued_at,
        }
        for i in db.scalars(
            select(Invoice)
            .where(Invoice.business_id == user.business_id)
            .order_by(Invoice.issued_at.desc())
        )
    ]


@router.get("/invoices/{id}")
def invoice(id: UUID, db: Db, user: CurrentUser):
    i = one(db, Invoice, id, user.business_id)
    return {
        "id": i.id,
        "invoice_number": i.invoice_number,
        "run_id": i.run_id,
        "status": i.status,
        "total_paise": i.total_paise,
        "issued_at": i.issued_at,
        "snapshot": i.snapshot,
    }


@router.get("/reports/sales")
def report(
    db: Db,
    user: CurrentUser,
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
):
    rows = db.execute(
        select(func.date(Payment.paid_at), func.sum(Payment.amount_paise))
        .where(
            Payment.business_id == user.business_id,
            Payment.status == "PAID",
            Payment.paid_at >= from_,
            Payment.paid_at <= to,
        )
        .group_by(func.date(Payment.paid_at))
        .order_by(func.date(Payment.paid_at))
    ).all()
    return [{"date": str(day), "total_paise": total} for day, total in rows]
