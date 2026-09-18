"""Deterministic stand-ins for Fareed's catalog/inventory/pricing APIs.

Fixed data only: the Manager must never invent a SKU, stock level, or price.
Replace these functions with real HTTP calls to Fareed's service once
`POST /catalog/match`, `POST /inventory/check`, and `POST /pricing/quote`
are live, keeping the same return shapes so callers don't change.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

CATALOG = [
    {
        "sku": "MCB-16A",
        "name": "MCB 16A",
        "category": "Circuit Protection",
        "aliases": ["mcb 16", "mcb-16", "16a mcb"],
        "unit": "pc",
        "unit_price": Decimal("180.00"),
        "stock_qty": 240,
        "reorder_threshold": 50,
    },
    {
        "sku": "MCB-32A",
        "name": "MCB 32A",
        "category": "Circuit Protection",
        "aliases": ["mcb 32", "mcb-32", "32a mcb", "32amp mcb"],
        "unit": "pc",
        "unit_price": Decimal("220.00"),
        "stock_qty": 12,
        "reorder_threshold": 25,
    },
    {
        "sku": "MCCB-63A",
        "name": "MCCB 63A",
        "category": "Circuit Protection",
        "aliases": ["mccb 63", "63a mccb"],
        "unit": "pc",
        "unit_price": Decimal("1450.00"),
        "stock_qty": 18,
        "reorder_threshold": 5,
    },
    {
        "sku": "CU-WIRE-1.5",
        "name": "Copper Wire 1.5mm",
        "category": "Wiring",
        "aliases": ["1.5mm wire", "copper wire 1.5", "1.5 sq mm wire"],
        "unit": "coil",
        "unit_price": Decimal("1250.00"),
        "stock_qty": 60,
        "reorder_threshold": 10,
    },
    {
        "sku": "CU-WIRE-2.5",
        "name": "Copper Wire 2.5mm",
        "category": "Wiring",
        "aliases": ["2.5mm wire", "copper wire 2.5", "2.5 sq mm wire"],
        "unit": "coil",
        "unit_price": Decimal("1850.00"),
        "stock_qty": 45,
        "reorder_threshold": 10,
    },
    {
        "sku": "LED-9W",
        "name": "LED Bulb 9W",
        "category": "Lighting",
        "aliases": ["led bulb 9w", "9w led", "led 9 watt"],
        "unit": "pc",
        "unit_price": Decimal("95.00"),
        "stock_qty": 500,
        "reorder_threshold": 100,
    },
    {
        "sku": "SW-SOCKET-CMB",
        "name": "Switch Socket Combo",
        "category": "Accessories",
        "aliases": ["switch socket", "socket combo"],
        "unit": "pc",
        "unit_price": Decimal("140.00"),
        "stock_qty": 300,
        "reorder_threshold": 60,
    },
    {
        "sku": "DB-8WAY",
        "name": "Distribution Board 8-way",
        "category": "Circuit Protection",
        "aliases": ["db 8 way", "8 way db", "distribution board 8way"],
        "unit": "pc",
        "unit_price": Decimal("2100.00"),
        "stock_qty": 8,
        "reorder_threshold": 5,
    },
    {
        "sku": "PVC-CONDUIT-25",
        "name": "PVC Conduit Pipe 25mm",
        "category": "Accessories",
        "aliases": ["conduit pipe 25mm", "25mm pipe", "pvc pipe 25"],
        "unit": "pc",
        "unit_price": Decimal("65.00"),
        "stock_qty": 400,
        "reorder_threshold": 80,
    },
    {
        "sku": "CABLE-TIE-PK",
        "name": "Cable Ties Pack",
        "category": "Accessories",
        "aliases": ["cable tie", "cable ties"],
        "unit": "pack",
        "unit_price": Decimal("55.00"),
        "stock_qty": 150,
        "reorder_threshold": 30,
    },
]

GST_RATE = Decimal("0.18")
APPROVAL_TOTAL_THRESHOLD = Decimal("50000.00")

_SEGMENT_SPLIT_RE = re.compile(r",|\n|\band\b|\bplus\b", re.IGNORECASE)
_LINE_RE = re.compile(r"^\s*(\d+)\s*(?:x|pcs?|units?|nos?)?\s*(.+?)\s*$")


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _find_candidates(text: str) -> list[dict]:
    needle = text.strip().lower()
    return [
        product
        for product in CATALOG
        if needle in product["name"].lower()
        or any(needle in alias for alias in product["aliases"])
        or product["name"].lower() in needle
        or any(alias in needle for alias in product["aliases"])
    ]


def match_line_items(raw_text: str) -> list[dict]:
    """Parse free text into line items against the fixed catalog.

    Returns one dict per detected line with match_status one of
    MATCHED, AMBIGUOUS, NOT_FOUND. Never fabricates a SKU.
    """
    segments = [s.strip() for s in _SEGMENT_SPLIT_RE.split(raw_text) if s.strip()]
    matches = [m for segment in segments if (m := _LINE_RE.match(segment))]
    if not matches:
        return [
            {
                "requested_text": raw_text.strip(),
                "quantity": None,
                "sku": None,
                "name": None,
                "unit": None,
                "match_status": "NOT_FOUND",
            }
        ]

    items = []
    for match in matches:
        qty_str, name_str = match.group(1), match.group(2)
        candidates = _find_candidates(name_str)
        if len(candidates) == 1:
            product = candidates[0]
            items.append(
                {
                    "requested_text": name_str.strip(),
                    "quantity": int(qty_str),
                    "sku": product["sku"],
                    "name": product["name"],
                    "unit": product["unit"],
                    "match_status": "MATCHED",
                }
            )
        elif len(candidates) > 1:
            items.append(
                {
                    "requested_text": name_str.strip(),
                    "quantity": int(qty_str),
                    "sku": None,
                    "name": None,
                    "unit": None,
                    "match_status": "AMBIGUOUS",
                    "candidates": [c["sku"] for c in candidates],
                }
            )
        else:
            items.append(
                {
                    "requested_text": name_str.strip(),
                    "quantity": int(qty_str),
                    "sku": None,
                    "name": None,
                    "unit": None,
                    "match_status": "NOT_FOUND",
                }
            )
    return items


def check_stock(line_items: list[dict]) -> list[dict]:
    by_sku = {p["sku"]: p for p in CATALOG}
    checked = []
    for item in line_items:
        if item["match_status"] != "MATCHED":
            checked.append(item)
            continue
        product = by_sku[item["sku"]]
        available = product["stock_qty"]
        requested = item["quantity"] or 0
        if available <= 0:
            stock_status = "OUT_OF_STOCK"
        elif available < requested:
            stock_status = "INSUFFICIENT"
        else:
            stock_status = "AVAILABLE"
        checked.append(
            {
                **item,
                "available_qty": available,
                "stock_status": stock_status,
                "low_stock": available <= product["reorder_threshold"],
            }
        )
    return checked


def quote(line_items: list[dict]) -> dict:
    by_sku = {p["sku"]: p for p in CATALOG}
    priced_items = []
    subtotal = Decimal("0")
    reason_codes = []

    for item in line_items:
        if item.get("stock_status") not in ("AVAILABLE", "INSUFFICIENT"):
            continue
        product = by_sku[item["sku"]]
        qty = item["quantity"] or 0
        line_total = product["unit_price"] * qty
        subtotal += line_total
        if item["stock_status"] == "INSUFFICIENT":
            reason_codes.append(f"INSUFFICIENT_STOCK:{item['sku']}")
        priced_items.append(
            {
                "sku": product["sku"],
                "name": product["name"],
                "quantity": qty,
                "unit": product["unit"],
                "unit_price": _money(product["unit_price"]),
                "line_total": _money(line_total),
            }
        )

    tax = (subtotal * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = subtotal + tax
    approval_required = total > APPROVAL_TOTAL_THRESHOLD or bool(reason_codes)
    if total > APPROVAL_TOTAL_THRESHOLD:
        reason_codes.append("TOTAL_ABOVE_APPROVAL_THRESHOLD")

    return {
        "items": priced_items,
        "subtotal": _money(subtotal),
        "tax": _money(tax),
        "total": _money(total),
        "currency": "INR",
        "approval_required": approval_required,
        "reason_codes": reason_codes,
    }
