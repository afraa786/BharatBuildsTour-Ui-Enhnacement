"""Guided WhatsApp catalog-browse -> cart -> checkout flow for buyers.

Pure helpers only: no DB access, no side effects. `runs/service.py` owns
persistence (BuyerCartSession) and wiring this into the buyer message
pipeline; this module just knows how to render the catalog/cart as
WhatsApp interactive payloads and how to parse the buyer's taps/replies.
"""

import re
from enum import StrEnum
from itertools import groupby

from app.modules.runs import mock_desks
from app.modules.whatsapp.client import build_button_interactive, build_list_interactive


class CartStep(StrEnum):
    IDLE = "IDLE"
    BROWSING = "BROWSING"
    AWAITING_QTY = "AWAITING_QTY"
    CART_MENU = "CART_MENU"


ITEM_ID_PREFIX = "item:"
ACTION_ADD_MORE = "action:add_more"
ACTION_VIEW_CART = "action:view_cart"
ACTION_CHECKOUT = "action:checkout"
ACTION_CLEAR_CART = "action:clear_cart"
QUOTE_ACTION_ACCEPT = "action:accept_quote"
QUOTE_ACTION_CHANGES = "action:request_changes"

_QTY_RE = re.compile(r"^\s*(\d+)")


def item_reply_id(sku: str) -> str:
    return f"{ITEM_ID_PREFIX}{sku}"


def parse_item_reply_id(reply_id: str | None) -> str | None:
    if not reply_id or not reply_id.startswith(ITEM_ID_PREFIX):
        return None
    sku = reply_id[len(ITEM_ID_PREFIX) :]
    by_sku = {product["sku"] for product in mock_desks.CATALOG}
    return sku if sku in by_sku else None


def parse_quantity(text: str) -> int | None:
    match = _QTY_RE.match(text or "")
    if not match:
        return None
    qty = int(match.group(1))
    return qty if qty > 0 else None


def build_catalog_sections() -> list[dict]:
    sections = []
    catalog_by_category = sorted(mock_desks.CATALOG, key=lambda p: p["category"])
    for category, products in groupby(catalog_by_category, key=lambda p: p["category"]):
        rows = [
            {
                "id": item_reply_id(product["sku"]),
                "title": product["name"][:24],
                "description": f"₹{product['unit_price']} / {product['unit']}"[:72],
            }
            for product in products
        ]
        sections.append({"title": category[:24], "rows": rows})
    total_rows = sum(len(section["rows"]) for section in sections)
    if total_rows > 10:
        raise ValueError(f"Catalog has {total_rows} rows, WhatsApp list messages cap at 10")
    return sections


def build_catalog_interactive() -> dict:
    return build_list_interactive(
        body="Browse our catalogue and tap an item to add it to your order.",
        button_text="View catalogue",
        sections=build_catalog_sections(),
        footer="StockAware",
    )


def build_cart_menu_interactive() -> dict:
    return build_button_interactive(
        body="Added to your cart. What next?",
        buttons=[
            (ACTION_ADD_MORE, "Add more"),
            (ACTION_VIEW_CART, "View cart"),
            (ACTION_CHECKOUT, "Checkout"),
        ],
    )


def build_view_cart_interactive() -> dict:
    return build_button_interactive(
        body="Your cart so far.",
        buttons=[
            (ACTION_ADD_MORE, "Add more"),
            (ACTION_CHECKOUT, "Checkout"),
            (ACTION_CLEAR_CART, "Clear cart"),
        ],
    )


def build_quote_action_interactive(quote_text: str) -> dict:
    return build_button_interactive(
        body=quote_text,
        buttons=[
            (QUOTE_ACTION_ACCEPT, "Accept quote"),
            (QUOTE_ACTION_CHANGES, "Request changes"),
        ],
    )


def find_product(sku: str) -> dict | None:
    return next((product for product in mock_desks.CATALOG if product["sku"] == sku), None)


def add_or_merge(cart: list[dict], sku: str, qty: int) -> list[dict]:
    product = find_product(sku)
    if product is None:
        return cart
    updated = list(cart)
    for line in updated:
        if line["sku"] == sku:
            line["qty"] += qty
            return updated
    updated.append(
        {
            "sku": sku,
            "name": product["name"],
            "unit": product["unit"],
            "unit_price": str(product["unit_price"]),
            "qty": qty,
        }
    )
    return updated


def cart_summary_text(cart: list[dict]) -> str:
    if not cart:
        return "Your cart is empty."
    lines = ["Your cart:"]
    total = 0
    for line in cart:
        line_total = line["qty"] * float(line["unit_price"])
        total += line_total
        lines.append(f"- {line['name']} x{line['qty']} {line['unit']} = ₹{line_total:.2f}")
    lines.append(f"Running total (excl. GST): ₹{total:.2f}")
    return "\n".join(lines)
