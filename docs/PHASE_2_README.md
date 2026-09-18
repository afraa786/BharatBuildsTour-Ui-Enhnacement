# StockAware Phase 2 — Catalog and Inventory

## Status and scope

Phase 2 adds read-only Fareed commercial APIs for product listing, exact catalog
resolution, and point-in-time inventory checks. PostgreSQL tables remain the
Phase 1 schema; **no Phase 2 migration** is required. This is not quote, order,
payment, or invoice functionality, and a stock check does not reserve stock.

The authoritative behavior is in [contracts.md](contracts.md). The independent
fixtures under `scratch/integration_harness/` are a QA oracle, not a replacement
for that contract.

## Internal access and business scope

Commercial routes fail closed until `INTERNAL_BUSINESS_ID` (a business UUID) and
`INTERNAL_SERVICE_TOKEN` are configured server-side. A trusted internal caller
sends `X-Internal-Service-Token`; the server maps that token to the configured
business. `business_id` in the POST body is a claim and must equal that scope,
but is never authorization by itself. Every database lookup includes the
authorized business ID. A wrong-business claim or product ID returns `NOT_FOUND`
without disclosing the foreign record. `GET /products` gets its business scope
only from the token, not a query parameter.

This single-business service-token gate is a narrow internal integration
measure, **not the final authentication system**. Keep these routes behind a
trusted network/HTTPS ingress; do not put this token in the Next.js browser,
WhatsApp messages, or a public repository. Service/actor authentication and
multi-business authorization remain an integration dependency.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/products` | Paginated active product listing; `limit` 1–200, `offset` >= 0, optional `include_inactive` for internal admin callers. |
| `POST` | `/catalog/match` | Exact normalized SKU, name, or declared-alias resolution. |
| `POST` | `/inventory/check` | Read-only stock classification for a known product and positive quantity. |

No Phase 3+ route is part of this phase. All three use the internal service
identity. Catalog/stock POST reads do not require `Idempotency-Key` because
they perform no mutation.

## Catalog behavior

The one canonical normalization utility applies Unicode NFKC, case folding,
then replaces punctuation/spacing runs with one space. Phase 1 demo seeding
uses the same utility for normalized product SKU/name/alias fields. This is an
**exact key match**, not fuzzy matching. Only active products in the authorized
business participate. Matches from SKU, name, and alias are combined by unique
product ID; no source is allowed to hide a second legitimate product. The
candidate list is ordered deterministically by SKU and ID. If a single product
matches multiple sources, the displayed source is SKU, then name, then alias.

- `MATCHED`: exactly one active product and compatible requested sellable unit;
  selected ID/SKU present.
- `AMBIGUOUS`: multiple products, or one product with unresolved unit meaning;
  selected ID/SKU **null**. `reason_code` is `MULTIPLE_MATCHES` or
  `UNIT_MISMATCH`.
- `NOT_FOUND`: no exact active match; selected ID/SKU null, candidates empty.

Aliases can intentionally point to multiple products. Substitutes are never
catalog matches. No cost, margin floor, or pricing-rule internals appear in
responses.

Example demo request:

```http
POST /catalog/match
X-Internal-Service-Token: <internal token>
Content-Type: application/json

{"business_id":"ff720599-56e8-53f4-9279-27ae059da37f","run_id":"RFQ-1042","requested_text":"  led-9w  ","requested_unit":"piece"}
```

The response has this shape (the UUID and SKU are deterministic demo data):

```json
{
  "status": "MATCHED",
  "requested_text": "  led-9w  ",
  "selected_product_id": "dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7",
  "selected_sku": "LED-9W",
  "reason": "Exact SKU match.",
  "reason_code": "EXACT_SKU_MATCH",
  "candidates": [{"product_id":"dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7","sku":"LED-9W","name":"9W LED Bulb","sellable_unit":"piece","stock_unit":"piece","pack_size":"1.000","match_type":"sku"}]
}
```

## Inventory behavior

`requested_qty` is a decimal **string** with at most three fractional digits,
strictly greater than zero. By default it is already in the product's canonical
`stock_unit`. An optional `requested_unit` can identify the sellable unit;
when it differs from the stock unit, only the explicit product `pack_size`
conversion is used. Unsupported units and fractional indivisible units return
422. The response quantity is normalized to the stock unit and encoded as a
three-decimal string.

Status precedence for a valid positive request:

1. On hand zero → `OUT_OF_STOCK`.
2. On hand below requested → `INSUFFICIENT_STOCK`.
3. Request fulfillable and hypothetical remainder at/below configured threshold
   → `LOW_STOCK`.
4. Otherwise → `AVAILABLE`.

Null reorder threshold never causes `LOW_STOCK`. Missing inventory for an
existing active product is an integrity failure (`INTERNAL_ERROR`), **not**
silently zero stock. `available_qty` equals current unreserved on-hand quantity;
there is no reservation balance. `checked_at` is UTC. The check does not write
inventory, movements, or row versions.

Example against the unmodified demo seed:

```http
POST /inventory/check
X-Internal-Service-Token: <internal token>
Content-Type: application/json

{"business_id":"ff720599-56e8-53f4-9279-27ae059da37f","run_id":"RFQ-1042","product_id":"dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7","requested_qty":"25.000"}
```

```json
{
  "status": "LOW_STOCK",
  "product_id": "dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7",
  "requested_qty": "25.000",
  "stock_unit": "piece",
  "on_hand_qty": "30.000",
  "available_qty": "30.000",
  "checked_at": "2026-09-18T00:00:00Z",
  "substitutes": []
}
```

`checked_at` above illustrates the ISO-8601 format; the real value is the UTC
time of the request. Stock values reflect current database rows, not guaranteed
seed values after operator changes.

On insufficient/out-of-stock results, explicitly configured substitutes may
appear, ranked by stored rank then SKU/ID. They must be active, in the same
business, have an inventory row and enough stock in the same stock unit. They
are suggestions only and never replace the requested product automatically.
The buyer/owner must confirm a replacement under the later quote workflow.

## Errors

Fareed commercial errors use the canonical envelope:

```json
{"error":{"code":"NOT_FOUND","message":"Product not found.","request_id":"req_<opaque>"}}
```

422 validation errors additionally include safe structured `details.errors`
when raised by request parsing. Authentication uses 401, unconfigured internal
authorization uses 503, and wrong-business resources use 404. Unexpected
errors are sanitized as `INTERNAL_ERROR` without SQL, stack traces, secrets,
or other-business data. Normal catalog `AMBIGUOUS`/`NOT_FOUND` and stock
`INSUFFICIENT_STOCK`/`OUT_OF_STOCK` are 200 business outcomes, not HTTP errors.

## For Rehbar

Pass the stable `run_id` and the authenticated business claim on each RFQ-driven
call. Send one line's `requested_text` and `requested_unit` to
`POST /catalog/match`. Only use `selected_product_id` when status is `MATCHED`.
For `AMBIGUOUS`, show the candidates and seek clarification; for `NOT_FOUND`,
ask the buyer to clarify without inventing an SKU. Send the selected product
ID and positive stock-unit quantity (or an explicit sellable `requested_unit`)
to `POST /inventory/check`.

`AVAILABLE` and `LOW_STOCK` are currently fulfillable observations; a low-stock
flag may be shown to the owner. `INSUFFICIENT_STOCK` and `OUT_OF_STOCK` need
clarification/substitute confirmation before proceeding. No Phase 2 result
reserves stock. Phase 4 payment-link creation must recheck it. These routes do
not advance Rehbar's run state or change the existing WhatsApp mock pipeline.

## For Frontend

Render `status`, `reason`/`reason_code`, candidate safe identifiers/name/unit,
and selected ID/SKU only when matched. Product list exposes ID, SKU, name,
sellable/stock units, pack size, indivisibility, base selling price in paise,
GST basis points, and active flag. Inventory exposes stock status, decimal
quantity strings, unit, UTC check timestamp, and ranked safe substitutes. Do
not compute authoritative prices, infer payment, or use the internal service
token in browser code; a server-side authenticated adapter is still required.

## Verification and remaining work

Phase 2 test files under `server/tests/test_phase2_*` exercise service behavior
through FastAPI and a disposable migrated PostgreSQL database, including
cross-business access and read-only invariants. Run `make test-pg`,
`make lint`, the harness validator/tests, `alembic check`, and Compose config
before checkpointing.

Phase 3 owns pricing/quotes and immutable commercial snapshots. Phase 4 owns
Razorpay, acceptance-bound payment links, stock recheck and verified payment.
Phase 5 owns invoice issuance and PDF artifacts. Production authorization,
business-confirmed stock/pricing/tax policy, and live provider verification
remain separate release gates.
