# Phase 2 Production API Contract

This document provides the adapter design for Phase 2 Catalog & Inventory, explaining how the JSON fixtures in `fixtures/` will map to actual live HTTP calls once Codex implements the backend.

## 1. POST /catalog/match

**Capability Name:** `catalog.match`

**Description:** Normalizes a buyer string (SKU, product name, or alias) and returns exact match candidates.

**Request:**
```json
{
  "business_id": "<uuid>",
  "run_id": "<string>",
  "requested_text": "<string>",
  "requested_unit": "<string>"
}
```

**Expected Response Invariant:**
- Must return 200 OK for MATCHED, AMBIGUOUS, and NOT_FOUND.
- Only exactly 1 match resolves to `selected_product_id` and `selected_sku`.
- `AMBIGUOUS` and `NOT_FOUND` MUST return `null` for selected identity.
- MUST NOT return `cost_unit_paise` or `min_margin_bps`.

**Required DB Setup:**
- Product definitions in the target `business_id` (active).
- Alias definitions linked to products.

**Expected DB Post-State:**
- Read-only. Database state must be unchanged.

---

## 2. POST /inventory/check

**Capability Name:** `inventory.check`

**Description:** Checks on-hand stock and threshold boundaries for a specific product and requested quantity.

**Request:**
```json
{
  "business_id": "<uuid>",
  "run_id": "<string>",
  "product_id": "<uuid>",
  "requested_qty": "<decimal string>"
}
```

**Expected Response Invariant:**
- Returns 200 OK for valid quantities.
- Returns 422 if `requested_qty <= 0` or precision > 3 decimals.
- Returns `OUT_OF_STOCK`, `INSUFFICIENT_STOCK`, `LOW_STOCK`, or `AVAILABLE`.
- Stock precedence: `OUT_OF_STOCK` > `INSUFFICIENT_STOCK` > `LOW_STOCK` > `AVAILABLE`.
- Includes ranked substitutes if the request is unfulfilled, isolated to the current business and active status.

**Required DB Setup:**
- Product definition and Inventory row matching `product_id`.
- Substitute definitions where applicable.

**Expected DB Post-State:**
- Read-only. Must not reserve stock or decrement `on_hand_qty`. Version number must remain unchanged. No new stock movements.
