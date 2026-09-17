"""Idempotent, demo-only seed data. Run with: python -m app.seed."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import transaction_session
from app.modules.catalog.models import Product, ProductAlias, ProductSubstitute
from app.modules.identity.models import Business
from app.modules.inventory.models import Inventory
from app.modules.pricing.models import PricingRule

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


def _normalize(value: str) -> str:
    """Stable demo lookup key; catalog matching itself belongs to Phase 2."""
    return " ".join("".join(char if char.isalnum() else " " for char in value.casefold()).split())


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
            "normalized_sku": _normalize(item.sku),
            "name": item.name,
            "normalized_name": _normalize(item.name),
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
            "id": _stable_id("alias", f"{item.sku}/{_normalize(alias)}"),
            "business_id": DEMO_BUSINESS_ID,
            "product_id": products_by_sku[item.sku],
            "alias_text": alias,
            "normalized_alias": _normalize(alias),
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
        business_id = seed_demo(session)
    print(f"Seeded demo business {business_id}; reruns preserve existing rows.")


if __name__ == "__main__":
    main()
