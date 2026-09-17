# StockAware Phase 1 — Backend Foundation

## 1. Phase 1 Status

`COMPLETE — FREEZE APPROVED`

Phase 1 passed an independent adversarial audit with:

- 0 Blockers
- 0 High findings
- 0 Medium findings
- 0 Low findings

This checkpoint completes the database foundation only. It does not mean the entire StockAware backend, commercial API surface, or quote-to-cash workflow is complete.

## 2. What Phase 1 Delivered

Phase 1 established:

- PostgreSQL commercial schema and reviewed Alembic migration
- SQLAlchemy models and an explicit metadata registry
- Database-level business/tenant isolation relationships
- Product, alias, substitute, and inventory persistence foundations
- Pricing-policy and immutable quote-version persistence foundations
- Payment, provider-event, and durable outbox persistence foundations
- Invoice identity, artifact state, and numbering-sequence foundations
- Mutation idempotency persistence
- Deterministic, repeatable demo seed data
- Explicit commit/rollback/close transaction lifecycle
- Real PostgreSQL migration, schema, seed, constraint, and transaction tests

The delivered code is a **database foundation**. Catalog matching, stock-check orchestration, pricing calculations, quote lifecycle services, Razorpay integration, invoice generation, and their HTTP APIs are **not implemented yet**.

The authoritative behavioral contract remains [contracts.md](contracts.md). See [phase1-schema.md](phase1-schema.md) for the detailed contract-to-schema mapping.

## 3. Database Tables

Phase 1 creates 17 commercial and support tables.

### Identity

- `businesses`: tenant identity and business-level configuration inputs.
- `buyers`: minimal business-scoped buyer/contact identity; not a CRM.

### Catalog

- `products`: canonical business-scoped SKUs, units, costs, prices, and configured GST rates.
- `product_aliases`: normalized aliases; one alias may intentionally produce multiple candidates.
- `product_substitutes`: explicit ranked alternatives, separate from exact matching.

### Inventory

- `inventory`: one current on-hand balance per business/product, with threshold and version fields.
- `stock_movements`: future auditable, idempotently keyed stock changes.

### Pricing & Quotes

- `pricing_rules`: versioned discount/margin policy inputs.
- `quote_lineages`: lockable `(business_id, run_id)` version lineage.
- `quotes`: one version-specific quote identity with buyer, policy, tax, totals, approval, and acceptance snapshots.
- `quote_items`: reproducible line-level quantity, price, discount, tax, and total snapshots.

### Payments

- `payments`: local payment intent/truth bound to an exact quote version and amount.
- `payment_events`: verified provider-event receipt metadata and replay identity.
- `payment_outbox`: durable post-payment handoff records; no consumer/transport exists yet.

### Invoices

- `invoices`: invoice identity, immutable commercial snapshot, and artifact state/reference.
- `invoice_sequences`: transactionally lockable sequence foundation per business/calendar year.

### Infrastructure

- `idempotency_keys`: business/action/key-scoped request fingerprint and replay result foundation.

## 4. Important Identifiers for Integration

| Identifier | Source / Owner | Purpose |
| --- | --- | --- |
| `business_id` | StockAware backend | Tenant/business identity |
| `run_id` | Rehbar | WhatsApp/RFQ workflow identity |
| `buyer_id` | StockAware backend | Canonical buyer identity |
| `product_id` | StockAware backend | Canonical product identity |
| `quote_id` | StockAware backend | Unique immutable quote-version identity |
| `quote_version` | StockAware backend | Sequential version within an RFQ lineage |
| `approval_id` | Rehbar | Owner-approval evidence identity |
| `acceptance_id` | Rehbar | Buyer-acceptance evidence identity |
| `payment_id` | StockAware backend | Internal payment identity |
| `provider_link_id` | Razorpay | Payment-provider link identity |
| `provider_event_id` | Razorpay | Provider webhook/event identity |
| `invoice_id` | StockAware backend | Internal invoice identity |
| `invoice_number` | StockAware backend | Human/business invoice number |

A revised quote receives a new `quote_id` and the next `quote_version` within the same `(business_id, run_id)` lineage. Previous quote versions are retained; they are never overwritten and cannot be used as the payment target once stale.

## 5. State Vocabularies

Integrations must use these exact uppercase values and must not invent alternatives.

### Quote

- `DRAFT`
- `GENERATED`
- `ACCEPTED`
- `EXPIRED`
- `CANCELLED`

Payment state is separate: quotes do not have `PAID` or `COMPLETED` states.

### Payment

- `CREATED`
- `PENDING`
- `PAID`
- `FAILED`
- `EXPIRED`
- `CANCELLED`

### Invoice

- `PENDING_ARTIFACT`
- `GENERATED`

## 6. Money & Quantity Contract

Money is stored and exchanged as integer paise. For example, ₹1,250.50 is `125050`. Quantities use PostgreSQL `NUMERIC(18,3)`. Pricing percentages and rates use basis points where specified by the contract.

Frontend and integration code must not independently calculate authoritative quote, payment, or invoice amounts with JavaScript floating-point arithmetic. The backend remains the source of truth for commercial calculations and will persist all rounded intermediate values.

## 7. For Rehbar / WhatsApp Integration

The intended lifecycle is:

```text
WhatsApp RFQ
  → run_id
  → catalog match
  → inventory check
  → quote
  → owner approval when required
  → buyer acceptance
  → payment link
  → provider-verified payment
  → invoice
```

Ready as a persistence/contract foundation:

- Stable `run_id` contract
- Quote-lineage and immutable quote-version storage
- Approval-evidence storage foundation
- Acceptance-evidence storage foundation
- Payment-event deduplication foundation
- Payment-outbox persistence foundation
- Stable cross-system identifiers

Not ready yet:

- WhatsApp ingress endpoint
- Catalog matching endpoint
- Inventory check endpoint
- Quote generation endpoint
- Approval application endpoint
- Acceptance application endpoint
- Payment-link endpoint
- Razorpay webhook endpoint
- Invoice generation endpoint
- `PaymentOutbox` consumer or transport

Rehbar continues to own WhatsApp ingress and run/workflow state. Fareed's backend will own the commercial outcomes; it must not infer approval, acceptance, or payment from an untrusted boolean or buyer message.

## 8. For Frontend Integration

Frontend work may safely design against:

- Stable identifier ownership
- Exact quote, payment, and invoice state vocabularies
- Integer-paise money representation
- Three-decimal quantity precision
- Immutable quote versions and new IDs on revision
- Separate quote, payment, and invoice states

The independent fixture suite at [`scratch/integration_harness/`](../scratch/integration_harness/) provides canonical examples for catalog and inventory responses, pricing calculations, quote lifecycle, payment-link flows, Razorpay events, invoice states, happy-path E2E flow, and failure journeys.

The harness is integration fixture and simulation data. It is **not** production backend implementation, does not connect to PostgreSQL, and does not prove the corresponding APIs exist.

## 9. Backend Endpoint Status

The application router currently registers only the two health routes below. FastAPI's documentation/schema routes are generated framework utilities.

| Endpoint / Capability | Phase | Current Status | Notes |
| --- | --- | --- | --- |
| `GET /health/live` | Foundation | AVAILABLE | Process liveness |
| `GET /health/ready` | Foundation | AVAILABLE | Executes `SELECT 1` against PostgreSQL |
| `GET /openapi.json` | Foundation | AVAILABLE | FastAPI-generated schema for currently registered routes |
| `GET /docs` | Foundation | AVAILABLE | FastAPI Swagger UI |
| `GET /redoc` | Foundation | AVAILABLE | FastAPI ReDoc UI |
| `GET /products` | Phase 2 | NOT IMPLEMENTED | Contracted product-list route |
| `POST /catalog/match` | Phase 2 | NOT IMPLEMENTED | Deterministic catalog matching |
| `POST /inventory/check` | Phase 2 | NOT IMPLEMENTED | Read-only availability check |
| `POST /pricing/quote` | Phase 3 | NOT IMPLEMENTED | Quote calculation/version creation |
| Quote approval application | Phase 3 | NOT IMPLEMENTED | Exact-version Rehbar evidence integration; transport remains deferred |
| Quote acceptance application | Phase 3 | NOT IMPLEMENTED | Exact-version buyer evidence integration; transport remains deferred |
| `POST /payments/create-link` | Phase 4 | NOT IMPLEMENTED | Razorpay Payment Link creation |
| `GET /payments/{id}` | Phase 4 | NOT IMPLEMENTED | Business-scoped payment read |
| `POST /payments/webhook` | Phase 4 | NOT IMPLEMENTED | Raw-body Razorpay signature verification required |
| `POST /invoice/generate` | Phase 5 | NOT IMPLEMENTED | Requires eligible verified payment |
| `GET /invoices/{id}` | Phase 5 | NOT IMPLEMENTED | Invoice/artifact read |
| Invoice PDF/artifact storage | Phase 5 | NOT IMPLEMENTED | Local adapter first; storage target remains deferred |

Rehbar-owned WhatsApp, admin-command, run, and timeline endpoints are also not implemented in this Fareed backend repository.

## 10. Phase 1 Data Safety Guarantees

The database currently enforces:

- Mandatory `business_id` on commercial records.
- Same-business composite foreign keys where child records reference domain identities.
- Business-scoped SKU and normalized-SKU uniqueness.
- Alias-to-product uniqueness while still permitting ambiguous aliases across products.
- Non-negative stored inventory and stock-movement result quantities.
- One current quote per `(business_id, run_id)` lineage.
- Unique quote version within each business/run lineage.
- Accepted-quote issuance timestamp and acceptance evidence requirements.
- Exact quote-version/run binding for payments and invoices.
- One `CREATED`, `PENDING`, or `PAID` payment per quote version.
- Provider reference/link/payment uniqueness and provider-event replay uniqueness.
- `PAID` payment provider identity and paid timestamp requirements.
- One invoice per payment and quote version, plus business-scoped invoice-number uniqueness.
- Invoice numbering counter foundation per business/year.
- Business/action/key idempotency uniqueness.
- `ON DELETE RESTRICT` on financial and historical relationships.

Later services must still enforce authorized caller scope, legal state transitions, current-version/expiry checks, amount matching, verified webhook evidence, invoice eligibility, concurrency locking, and atomic inventory mutations. Schema constraints complement those rules; they do not replace service logic.

## 11. Demo Seed

With PostgreSQL configured and migrated, run:

```bash
make seed
```

The current seed contains:

- 1 demo business
- 11 products
- 17 aliases
- 1 substitute mapping
- 11 inventory rows
- 1 pricing rule

These are **DEMO fixtures**. They are not production pricing, tax, margin, discount, low-stock, or inventory policy.

The seed uses deterministic IDs and PostgreSQL conflict handling, is safe to run repeatedly, and does not overwrite existing operator-editable inventory or pricing-policy values.

## 12. Local Development

Create local configuration once and replace the placeholder password:

```bash
cp .env.example .env
make install
make hooks
```

Run and inspect services:

```bash
make up
docker compose ps
curl http://localhost:${API_PORT:-8000}/health/live
curl http://localhost:${API_PORT:-8000}/health/ready
```

Migration and seed commands:

```bash
make migrate
cd server && .venv/bin/alembic current
cd server && .venv/bin/alembic check
make seed
```

Test and quality commands:

```bash
make test
make test-pg
make lint
server/.venv/bin/ruff format --check server
server/.venv/bin/pre-commit run --all-files
docker compose config --quiet
git diff --check
```

The PostgreSQL suite creates a uniquely named temporary database, exercises the real Alembic migration, and removes that database afterward. Never point it at a database name it did not create.

The independent fixture harness can be checked separately:

```bash
server/.venv/bin/python scratch/integration_harness/validator.py
server/.venv/bin/pytest -c scratch/integration_harness/pytest.ini scratch/integration_harness/tests
```

## 13. Testing / Verification

The frozen Phase 1 checkpoint was verified with:

- Default backend suite: 3 passed, 6 PostgreSQL-only tests skipped, 2 non-failing warnings.
- PostgreSQL suite: 9 passed with a real PostgreSQL database, 2 non-failing warnings.
- Actual migration upgrade, downgrade to `0001_baseline`, and re-upgrade to head.
- Alembic model/schema drift check.
- Actual seed CLI executed twice with stable logical row counts.
- Commit-on-success and rollback-on-failure transaction tests.
- Cross-business foreign-key and business-scoped uniqueness tests.
- Integer-paise and decimal-quantity constraint tests.
- Duplicate provider-event, invoice, and idempotency-key rejection tests.
- Docker Compose configuration, healthy PostgreSQL, and successful readiness query.
- Ruff lint and formatting checks.
- Configured pre-commit checks, including private-key and secret detection.
- `git diff --check`.

The two warnings come from upstream Starlette/httpx TestClient deprecations and do not fail the suite.

## 14. Deferred Items

The following are intentionally outside Phase 1 and are not Phase 1 bugs:

- Authentication and business authorization
- Catalog matching and inventory service logic
- Pricing and quote service logic
- Rehbar approval/acceptance transport
- Payment Link creation
- Razorpay webhook processing
- `PaymentOutbox` consumer/transport
- Invoice generation and eligibility service
- PDF generation and artifact storage
- Stock deduction timing and post-payment shortage resolution
- Production pricing and discount/margin thresholds
- Production low-stock thresholds
- GST invoice classification and legal requirements
- Live Razorpay credentials and multi-account routing

## 15. Next Phase

Phase 2 is **Catalog + Inventory**. At a high level it will add:

- Deterministic `MATCHED`, `AMBIGUOUS`, and `NOT_FOUND` catalog outcomes
- Exact SKU/name and alias matching without invented selections
- Unit/pack mismatch handling
- Strict business isolation in every repository operation
- Read-only inventory checks
- `AVAILABLE`, `LOW_STOCK`, `INSUFFICIENT_STOCK`, and `OUT_OF_STOCK` outcomes
- Explicit substitute suggestions that never silently replace a requested SKU
- PostgreSQL integration tests
- Compatibility with the canonical integration harness

Phase 2 is not implemented as part of this checkpoint.

## 16. Source-of-Truth Documents

- [contracts.md](contracts.md): authoritative business and integration contract.
- [build-plan.md](build-plan.md): product requirements and ownership boundaries.
- [backend-implementation-plan.md](backend-implementation-plan.md): dependency-aware implementation sequence.
- [phase1-schema.md](phase1-schema.md): detailed Phase 1 schema mapping and index rationale.
- [`scratch/integration_harness/`](../scratch/integration_harness/): canonical illustrative fixtures and simulations; subordinate to `contracts.md`.

When documentation, fixtures, and implementation appear to disagree, stop and reconcile them against `contracts.md`; do not silently invent a business rule.
