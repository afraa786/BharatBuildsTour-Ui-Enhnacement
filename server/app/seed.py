"""Idempotent, demo-only seed data. Run with: python -m app.seed."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import transaction_session
from app.modules.catalog.models import Product, ProductAlias, ProductSubstitute
from app.modules.catalog.normalization import normalize_catalog_text
from app.modules.identity.models import Business, Buyer
from app.modules.identity.owner_models import Category, User
from app.modules.inventory.models import Inventory
from app.modules.invoices.models import Invoice
from app.modules.payments.models import Payment
from app.modules.pricing.models import PricingRule, Quote, QuoteLineage
from app.modules.runs.models import Run

DEMO_BUSINESS_ID = uuid5(NAMESPACE_URL, "stockaware/demo/business/v1")
DEMO_RULE_ID = uuid5(NAMESPACE_URL, "stockaware/demo/pricing-rule/v1")
DEMO_EFFECTIVE_FROM = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class DemoProduct:
    sku: str
    name: str
    sellable_unit: str
    stock_unit: str
    pack_size: str
    cost_paise: int
    price_paise: int
    gst_bps: int
    on_hand: str
    reorder_threshold: str
    aliases: tuple[str, ...]


# These amounts, GST rates, thresholds, and aliases are fixtures, not live business policy.
DEMO_PRODUCTS = (
    DemoProduct(
        "MCB-32A-SP",
        "32A Single Pole MCB",
        "piece",
        "piece",
        "1",
        12500,
        18000,
        1800,
        "24",
        "5",
        ("32 amp mcb", "32a sp mcb"),
    ),
    DemoProduct(
        "MCB-32A-DP",
        "32A Double Pole MCB",
        "piece",
        "piece",
        "1",
        26000,
        35000,
        1800,
        "10",
        "2",
        ("32 amp mcb", "32a dp mcb"),
    ),
    DemoProduct(
        "CABLE-2P5SQ-90M",
        "2.5 sq mm Copper Wire 90m Coil",
        "coil",
        "coil",
        "1",
        125000,
        170000,
        1800,
        "8",
        "2",
        ("2.5 sq mm wire", "2.5mm copper coil"),
    ),
    DemoProduct(
        "SWITCH-6A-1W",
        "6A One-Way Modular Switch",
        "piece",
        "piece",
        "1",
        4500,
        7500,
        1800,
        "60",
        "10",
        ("6a switch", "one way modular switch"),
    ),
    DemoProduct(
        "SOCKET-6A",
        "6A Modular Socket",
        "piece",
        "piece",
        "1",
        5500,
        9000,
        1800,
        "40",
        "10",
        ("6a socket",),
    ),
    DemoProduct(
        "LED-9W",
        "9W LED Bulb",
        "piece",
        "piece",
        "1",
        7000,
        12000,
        1800,
        "30",
        "5",
        ("9 watt led", "9w bulb"),
    ),
    DemoProduct(
        "LED-12W",
        "12W LED Bulb",
        "piece",
        "piece",
        "1",
        9000,
        15000,
        1800,
        "18",
        "4",
        ("12 watt led", "12w bulb"),
    ),
    DemoProduct(
        "CONDUIT-20MM-3M",
        "20mm PVC Conduit 3m",
        "piece",
        "piece",
        "1",
        4500,
        7000,
        1800,
        "50",
        "10",
        ("20mm conduit",),
    ),
    DemoProduct(
        "SCREW-M4-25-P100",
        "M4 x 25mm Machine Screws Pack of 100",
        "pack",
        "piece",
        "100",
        8000,
        12000,
        1800,
        "2000",
        "300",
        ("m4 25 screw pack",),
    ),
    DemoProduct(
        "TAPE-INSUL-19MM",
        "19mm Electrical Insulation Tape",
        "roll",
        "roll",
        "1",
        1500,
        2500,
        1800,
        "100",
        "20",
        ("insulation tape",),
    ),
    DemoProduct(
        "CONTACTOR-25A-3P",
        "25A Three-Pole Contactor",
        "piece",
        "piece",
        "1",
        85000,
        110000,
        1800,
        "3",
        "2",
        ("25a contactor",),
    ),
)


def _stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"stockaware/demo/{kind}/{key}")


def seed_demo(session: Session) -> UUID:
    """Insert missing demo rows without overwriting stock or owner edits.

    The caller owns the transaction; a failed seed rolls back as one unit.
    """
    session.execute(
        insert(Business)
        .values(
            id=DEMO_BUSINESS_ID,
            display_name="StockAware Demo Electrical & Hardware",
            currency="INR",
            timezone="Asia/Kolkata",
            quote_validity_minutes=1440,
            approval_required_for_all=True,
            is_demo=True,
        )
        .on_conflict_do_nothing()
    )
    business = session.get(Business, DEMO_BUSINESS_ID)
    if business is None or not business.is_demo:
        raise RuntimeError("Demo business ID is occupied by non-demo data")

    product_rows = [
        {
            "id": _stable_id("product", item.sku),
            "business_id": DEMO_BUSINESS_ID,
            "sku": item.sku,
            "normalized_sku": normalize_catalog_text(item.sku),
            "name": item.name,
            "normalized_name": normalize_catalog_text(item.name),
            "sellable_unit": item.sellable_unit,
            "stock_unit": item.stock_unit,
            "pack_size": Decimal(item.pack_size),
            "indivisible": True,
            "cost_unit_paise": item.cost_paise,
            "base_unit_price_paise": item.price_paise,
            "gst_rate_bps": item.gst_bps,
            "active": True,
        }
        for item in DEMO_PRODUCTS
    ]
    session.execute(insert(Product).values(product_rows).on_conflict_do_nothing())

    products_by_sku = dict(
        session.execute(
            select(Product.sku, Product.id).where(Product.business_id == DEMO_BUSINESS_ID)
        ).all()
    )
    missing = {item.sku for item in DEMO_PRODUCTS} - products_by_sku.keys()
    if missing:
        raise RuntimeError(f"Demo product SKU conflict: {sorted(missing)}")

    aliases = [
        {
            "id": _stable_id("alias", f"{item.sku}/{normalize_catalog_text(alias)}"),
            "business_id": DEMO_BUSINESS_ID,
            "product_id": products_by_sku[item.sku],
            "alias_text": alias,
            "normalized_alias": normalize_catalog_text(alias),
        }
        for item in DEMO_PRODUCTS
        for alias in item.aliases
    ]
    session.execute(insert(ProductAlias).values(aliases).on_conflict_do_nothing())

    inventory = [
        {
            "business_id": DEMO_BUSINESS_ID,
            "product_id": products_by_sku[item.sku],
            "on_hand_qty": Decimal(item.on_hand),
            "reorder_threshold": Decimal(item.reorder_threshold),
            "version": 1,
        }
        for item in DEMO_PRODUCTS
    ]
    session.execute(insert(Inventory).values(inventory).on_conflict_do_nothing())

    session.execute(
        insert(PricingRule)
        .values(
            id=DEMO_RULE_ID,
            business_id=DEMO_BUSINESS_ID,
            version=1,
            max_discount_bps=1000,
            min_margin_bps=1500,
            active=True,
            effective_from=DEMO_EFFECTIVE_FROM,
            is_demo=True,
        )
        .on_conflict_do_nothing()
    )
    rule = session.get(PricingRule, DEMO_RULE_ID)
    if rule is None or not rule.is_demo:
        raise RuntimeError("Demo pricing rule conflicts with an existing rule")

    session.execute(
        insert(ProductSubstitute)
        .values(
            id=_stable_id("substitute", "LED-9W/LED-12W"),
            business_id=DEMO_BUSINESS_ID,
            product_id=products_by_sku["LED-9W"],
            substitute_product_id=products_by_sku["LED-12W"],
            rank=1,
            reason="Demo alternative wattage; requires buyer confirmation",
        )
        .on_conflict_do_nothing()
    )
    return DEMO_BUSINESS_ID


def main() -> None:
    with transaction_session() as session:
        business_id = seed_owner_demo(session)
    print(f"Seeded owner demo business {business_id}; reruns preserve existing rows.")


# Owner-dashboard data is deliberately deterministic so repeated demo runs are safe.

OWNER_PHONE = "8766700429"
OWNER_NAME = "Rehbar Khan"
OWNER_CATEGORIES = ("Switchgear", "Cables & Wires", "Lighting")
OWNER_BUYERS = (
    ("Sharma Electricals", "+919810000001", "customer", "WhatsApp"),
    ("Kumar & Sons", "+919810000002", "customer", "Referral"),
    ("Brightline Infra", "+919810000003", "customer", "Trade fair"),
    ("Aarav Traders", "+919810000004", "lead", "Website"),
    ("Mehta Electrical", "+919810000005", "lead", "WhatsApp"),
)
OWNER_RUNS = (
    ("DEMO-OWNER-1001", "pending", "Aarav Traders", "+919810000004", 7),
    ("DEMO-OWNER-1002", "shipped", "Sharma Electricals", "+919810000001", 2),
    ("DEMO-OWNER-1003", "paid", "Kumar & Sons", "+919810000002", 4),
    ("DEMO-OWNER-1004", "cancelled", "Mehta Electrical", "+919810000005", None),
)


def seed_owner_dashboard(session: Session, business_id: UUID) -> None:
    """Add the owner-facing demo records without modifying existing business data."""
    user = session.scalar(select(User).where(User.phone_number == OWNER_PHONE))
    if user is None:
        session.add(
            User(
                id=_stable_id("user", OWNER_PHONE),
                business_id=business_id,
                phone_number=OWNER_PHONE,
                name=OWNER_NAME,
            )
        )
    elif user.business_id != business_id:
        raise RuntimeError("Owner phone number belongs to another business")
    categories: dict[str, Category] = {}
    for name in OWNER_CATEGORIES:
        category = session.scalar(
            select(Category).where(Category.business_id == business_id, Category.name == name)
        )
        if category is None:
            category = Category(id=_stable_id("category", name), business_id=business_id, name=name)
            session.add(category)
            session.flush()
        categories[name] = category
    for index, product in enumerate(
        session.scalars(
            select(Product).where(Product.business_id == business_id).order_by(Product.sku)
        ).all()
    ):
        if product.category_id is None:
            product.category_id = categories[OWNER_CATEGORIES[index % len(OWNER_CATEGORIES)]].id
    for name, phone, buyer_type, source in OWNER_BUYERS:
        buyer = session.scalar(
            select(Buyer).where(Buyer.business_id == business_id, Buyer.whatsapp_e164 == phone)
        )
        if buyer is None:
            session.add(
                Buyer(
                    id=_stable_id("buyer", phone),
                    business_id=business_id,
                    display_name=name,
                    whatsapp_e164=phone,
                    is_customer=buyer_type == "customer",
                    source=source,
                )
            )
    session.flush()
    now = datetime.now(UTC)
    for run_id, status, buyer_name, phone, days in OWNER_RUNS:
        run = session.scalar(select(Run).where(Run.run_id == run_id))
        if run is None:
            session.add(
                Run(
                    id=_stable_id("run", run_id),
                    run_id=run_id,
                    business_id=business_id,
                    status=status,
                    source="owner_demo",
                    buyer_name=buyer_name,
                    buyer_wa_id=phone,
                    raw_text="Owner dashboard demo RFQ",
                    line_items=[
                        {"name": "Demo electrical item", "quantity": 2, "unit_price_paise": 18000}
                    ],
                    quote_snapshot={"status": status, "total_paise": 36000, "currency": "INR"},
                    expected_delivery_date=(now + timedelta(days=days))
                    if days is not None
                    else None,
                )
            )


def seed_owner_demo(session: Session) -> UUID:
    business_id = seed_demo(session)
    seed_owner_dashboard(session, business_id)
    seed_owner_billing(session, business_id)
    return business_id


# Paid quote/payment/invoice chain used by Billing and Sales Reports demonstrations.


def seed_owner_billing(session: Session, business_id: UUID) -> None:
    rule = session.scalar(
        select(PricingRule).where(
            PricingRule.business_id == business_id, PricingRule.active.is_(True)
        )
    )
    if rule is None:
        raise RuntimeError("Owner billing seed requires an active pricing rule")
    for number, run_code, phone in (
        (1, "DEMO-OWNER-1002", "+919810000001"),
        (2, "DEMO-OWNER-1003", "+919810000002"),
    ):
        buyer = session.scalar(
            select(Buyer).where(Buyer.business_id == business_id, Buyer.whatsapp_e164 == phone)
        )
        quote_id = _stable_id("owner-quote", run_code)
        payment_id = _stable_id("owner-payment", run_code)
        invoice_id = _stable_id("owner-invoice", run_code)
        session.execute(
            insert(QuoteLineage)
            .values(business_id=business_id, run_id=run_code, latest_version=1)
            .on_conflict_do_nothing()
        )
        quote = session.get(Quote, quote_id)
        if quote is None:
            quote = Quote(
                id=quote_id,
                business_id=business_id,
                run_id=run_code,
                quote_version=1,
                is_current=True,
                buyer_id=buyer.id,
                buyer_snapshot={"name": buyer.display_name, "phone": phone},
                pricing_rule_id=rule.id,
                pricing_rule_version=rule.version,
                policy_snapshot={"demo": True},
                tax_context_snapshot=None,
                status="DRAFT",
                currency="INR",
                subtotal_paise=36000,
                tax_paise=0,
                total_paise=36000,
                approval_required=False,
                approval_satisfied=False,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            session.add(quote)
        session.flush()
        payment = session.get(Payment, payment_id)
        if payment is None:
            payment = Payment(
                id=payment_id,
                business_id=business_id,
                run_id=run_code,
                quote_id=quote_id,
                quote_version=1,
                status="PAID",
                amount_paise=36000,
                currency="INR",
                provider_account_key="owner-demo",  # pragma: allowlist secret
                provider_reference_id=f"owner-demo-ref-{number}",
                provider_payment_id=f"owner-demo-paid-{number}",
                link_expires_at=datetime.now(UTC) + timedelta(days=30),
                paid_at=datetime.now(UTC),
            )
            session.add(payment)
        session.flush()
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            session.add(
                Invoice(
                    id=invoice_id,
                    business_id=business_id,
                    run_id=run_code,
                    quote_id=quote_id,
                    quote_version=1,
                    payment_id=payment_id,
                    invoice_number=f"INV-2026-{900000 + number:06d}",
                    status="PENDING_ARTIFACT",
                    currency="INR",
                    total_paise=36000,
                    snapshot={"buyer_name": buyer.display_name, "run_id": run_code},
                )
            )
        run = session.scalar(
            select(Run).where(Run.run_id == run_code, Run.business_id == business_id)
        )
        run.quote_id, run.payment_id, run.invoice_id = (
            str(quote_id),
            str(payment_id),
            str(invoice_id),
        )


if __name__ == "__main__":
    main()
