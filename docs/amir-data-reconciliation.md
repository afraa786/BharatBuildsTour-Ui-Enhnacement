# Amir data reconciliation

This is a read-only reconciliation of the current repository against Amir's
canonical demo truth table. It intentionally does not rewrite teammate-owned
fixtures, seed code, workflow code, or the UI. The canonical contract is in
`fixtures/canonical-demo-data.json`.

## Canonical values

| SKU | Name | Alias | Price | Stock | Unit | Status |
|---|---|---|---:|---:|---|---|
| `MCB32` | 32A MCB | 32 amp MCB | ₹450 | 8 | each | LOW |
| `MCB16` | 16A MCB | 16 amp MCB | ₹280 | 50 | each | OK |
| `WIRE25` | 2.5mm Wire | 2.5 sq mm wire | ₹1,850 | 0 | metre | OUT |
| `LED9` | 9W LED | 9 watt bulb | ₹90 | 100 | each | OK |

Prices are shown in rupees here and as integer paise in the canonical JSON.
Thresholds are demo-only values added to make LOW/OUT alerts reproducible; the
production inventory owner still needs to approve threshold semantics.

## Conflicts found

| Source | What conflicts | Current values | Canonical / expected | Owner or decision | Demo impact |
|---|---|---|---|---|---|
| `fixtures/inventory-demo.csv` | SKU IDs, names, prices, stock, and aliases differ for all four truth-table products | Uses `MCB-32A-SP`, `MCB-16A-SP`, `LED-9W`, and no `WIRE25`; e.g. `MCB-32A-SP` ₹260, stock 42; `LED-9W` ₹75, stock 23 | `MCB32` ₹450/8, `MCB16` ₹280/50, `WIRE25` ₹1,850/0, `LED9` ₹90/100 | Amir + Fareed must decide whether the shared CSV is migrated to canonical IDs | Importers and UI mocks can show different products and alerts |
| `server/app/api/routes/demo.py` | Demo API catalog uses a third set of IDs, prices, and stock | `MCB-32A-SP` ₹260/38, `LED-9W` ₹75/20; no MCB16 or WIRE25 | Canonical four SKUs and values | Fareed owns API catalog contract; coordinate before changing it | Endpoint responses do not match canonical demo screenshots |
| `server/app/seed.py` | PostgreSQL seed has a fourth catalog and different units/values | `MCB-32A-SP` ₹180/24, `LED-9W` ₹120/30, `CABLE-2P5SQ-90M` coil; no MCB32/MCB16/WIRE25 | Canonical values, only if Fareed approves a seed migration | Fareed owns persistence seed and database field contract | `make seed` cannot reproduce the Amir demo world |
| `server/app/modules/runs/mock_desks.py` | Workflow mock catalog uses different names, aliases, IDs, units, prices, and thresholds | `MCB-32A` ₹220/12 `pc`, `CU-WIRE-2.5` ₹1,850/45 `coil`, `LED-9W` ₹95/500 `pc` | Canonical IDs/units/values | Rehbar/Fareed own workflow and catalog integration | WhatsApp run states and quote totals differ from fixtures |
| `scratch/integration_harness/fixtures/products.json` | Harness uses generic `SKU-001`… IDs and different product values | `SKU-001` Copper Wire 2.5mm, `SKU-003` LED 9W at ₹80, `meter`/`piece` | Canonical values for Amir-facing demos; harness remains illustrative until team adopts the contract | Fareed owns harness API contracts; team decision required | Harness tests are not directly replayable against canonical demo data |
| `fixtures/workflow-cases.json` | RFQ IDs and expected states are from the earlier fixture world | `RUN-DEMO-1001`…`1005`, `MCB-32A-SP`, `LED-9W`, status names such as `SENT`, `PAID`, `GENERATED` | Canonical RFQ IDs and scenario IDs in `canonical-demo-data.json`; preserve existing cases until migration is agreed | Rehbar/Fareed decide run/quote status contract | Docs, API mocks, and canonical scenarios refer to different records |
| `fixtures/vendor-message-examples.json` | Vendor events refer to non-canonical SKUs | Affected SKUs include `LED-9W`, `LED-12W`, `RCCB-40A-DP`, and `WIRE-1.5SQ-*` | Canonical vendor examples use `MCB32` and `WIRE25`; existing examples remain useful parser samples | Amir owns message examples; vendor event schema needs team agreement | Vendor alerts cannot be joined to canonical products without a mapping |
| `scratch/integration_harness/fixtures/ids.json` and entity fixtures | Deterministic IDs use harness-owned UUID-like records | `RFQ-1042-ALPHA`, `q...`, `p...`, `i...`, `INV-2026-000001` | Canonical IDs are `RFQ-DEMO-*`, `QT-DEMO-*`, `PAY-DEMO-*`, `INV-DEMO-001` | Rehbar/Fareed own persisted identifiers; do not alias silently | Cross-linking a demo timeline to invoice/payment fixtures is ambiguous |
| `server/app/api/routes/demo.py` and `server/app/modules/runs/state_machine.py` | Status vocabularies differ | Demo API uses `QUOTED`, `ACCEPTED`, `PAID`, `INVOICED`; state machine uses `QUOTE_SENT`, `PAYMENT_PENDING`, `PAYMENT_CONFIRMED`, `INVOICE_GENERATED` | Canonical JSON preserves the endpoint vocabulary where records are examples and labels scenario intent separately | Rehbar owns state-machine contract | QA assertions can pass against one surface and fail against another |
| `server/app/api/routes/demo.py` payment confirmation route | Router prefix is `/demo`, but decorator includes `/demo` again | Declared path becomes `/demo/demo/payments/{payment_id}/confirm`; README/test expectations use `/demo/payments/{payment_id}/confirm` | Needs a team-owned route decision before integration | Fareed/Rehbar own endpoint behavior; Amir only records the mismatch | Payment-confirmation demo and test calls can 404 |

## Reconciliation rules

1. Treat the canonical JSON as Amir's demo/data handoff, not as permission to
   mutate another owner's source of truth.
2. Use stable canonical SKU IDs when creating new Amir fixtures. Add an explicit
   mapping when an existing API must retain another ID.
3. Resolve price, stock, unit, threshold, status, and ID decisions with the
   owning teammate before changing integration code.
4. Until those decisions are made, label cross-source demos PARTIAL or BLOCKED
   rather than presenting them as one coherent end-to-end flow.
