# StockAware Commerce OS

WhatsApp-first quote-to-cash system for wholesalers. This repository currently contains the application foundation and a Next.js starter; business workflows are the next implementation phase.

| Path | Purpose | Owner |
| --- | --- | --- |
| `server/` | FastAPI, catalog, inventory, pricing, payment, invoice, PostgreSQL | Fareed |
| `client/` | Next.js onboarding, control room, and buyer pages | Yunus |
| `docs/` | Architecture, contracts, implementation checklist | Shared |
| `compose.yaml` | Local PostgreSQL, migration runner, FastAPI | Shared |

Read [the build plan](docs/build-plan.md) before adding endpoints. It explains setup, ownership, schema decisions, API contracts, and the exact build order.

## Quick start

1. Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD` with a unique local value. If port 8000 is occupied, set `API_PORT=8001`.
2. Run `docker compose up --build -d` from the repository root.
3. Open `http://localhost:<API_PORT>/docs`, `/health/live`, and `/health/ready` (default port 8000).
4. Run the frontend separately with `cd client && npm install && npm run dev`.

The Compose database data persists in the `postgres_data` volume. `docker compose down` stops services and keeps that volume. Do not use `docker compose down -v` unless you intend to delete local database data.

For local Python development and hooks, run `make install` and `make hooks`, then `make lint` and `make test`. See the build plan for migration and deployment details.

## Fareed's backend work: research-agent checklist

Your ownership is in server/: product truth, stock truth, pricing policy, Razorpay payment, invoice issuance, and PostgreSQL. This repository currently has the FastAPI and database foundation; commercial endpoints below still need implementation. Use the detailed [build plan](docs/build-plan.md) for proposed schemas, routes, and acceptance cases.

### 1. Freeze the team contracts

- [ ] Ask Rehbar for the normalized RFQ payload: run ID, buyer/business IDs, requested names, quantities, units, delivery context, and source message ID.
- [ ] Decide who records owner approval and buyer quote acceptance. Payment creation must receive the exact quote version and approval/action ID.
- [ ] Agree on quote, payment, invoice, and error JSON with Rehbar and Yunus before coding endpoints.
- [ ] Ask Amir for realistic products, aliases, RFQs, stock failures, pricing exceptions, and payment retry fixtures.
- [ ] Decide whether every table gets a business ID now, even though the MVP demo uses one wholesaler.

### 2. Design the PostgreSQL schema

- [ ] Model businesses, products, SKU aliases, substitutes, inventory, pricing rules, quotes, quote items, payments, provider events, invoices, and idempotency keys.
- [ ] Add uniqueness constraints for business + SKU, provider event ID, payment request key, invoice number, and invoice per paid payment.
- [ ] Define units, pack sizes, stock precision, UTC timestamps, and money representation. Use integer paise or PostgreSQL NUMERIC with Decimal calculations.
- [ ] Add SQLAlchemy models in server/app/modules, register them for Alembic, and create a reviewed migration.
- [ ] Write an idempotent seed command for 8–15 demo products and stock rows.

### 3. Implement catalog and stock

- [ ] GET /products: stable catalog fields for the admin UI.
- [ ] POST /catalog/match: normalize buyer names and aliases; return matched, ambiguous, or not found with candidates. Never invent a SKU.
- [ ] POST /inventory/check: return available quantity, shortage, low-stock signal, and suitable substitutes.
- [ ] Agree with Rehbar when stock is reserved or deducted. A quote check should only read stock.

### 4. Implement pricing and quotes

- [ ] POST /pricing/quote: calculate line prices, subtotal, GST, and grand total from stored inputs.
- [ ] Store a product price and pricing-rule snapshot so the saved quote can be reproduced later.
- [ ] Define discount cap, margin floor, quote expiry, and customer tier rules with the first wholesaler.
- [ ] Return approval_required and reason codes for policy exceptions; bind approval to quote ID and version.
- [ ] Confirm GST and invoice requirements with the business/accounting owner before issuing real tax invoices.

### 5. Implement Razorpay payments

- [ ] POST /payments/create-link: only an accepted, unexpired, approved quote can create a link for its exact stored amount and currency.
- [ ] Persist local payment ID, provider link ID, amount, status, and idempotency key. Add GET /payments/{id} for safe UI status.
- [ ] POST /payments/webhook: verify the signature over the raw request body, then match provider IDs, amount, currency, and event type.
- [ ] Deduplicate provider events in PostgreSQL. A buyer message saying paid must never change payment status.

### 6. Implement invoices

- [ ] POST /invoice/generate: require verified payment for the same quote; allocate one invoice number and immutable commercial snapshot.
- [ ] Generate the PDF, store an artifact reference in PostgreSQL, and keep storage replaceable by S3 later.
- [ ] GET /invoices/{id} and resend: return the existing invoice on retries, without issuing a second invoice.

### 7. Prove integration is safe

- [ ] Test alias ambiguity, wrong units, low stock, unsafe discount, stale approval, expired quote, invalid signature, amount mismatch, and duplicate events.
- [ ] Test invoice rejection before payment and idempotent invoice return after verified payment.
- [ ] Run one JSON-driven end-to-end case against PostgreSQL and share sample requests/responses with Rehbar and Yunus.
- [ ] Run make lint, make test, and the pre-commit checks before handoff.

### Other team owners

| Owner | Their responsibility |
| --- | --- |
| Rehbar | WhatsApp webhook, Manager/run lifecycle, approval capture, accepted-quote trigger, audit timeline |
| Yunus | Next.js onboarding, inventory UI, control room, buyer quote/payment/invoice pages |
| Amir | Fixtures, alerts/reminders, QA cases, and demo support |

The frontend displays saved backend results. It does not decide authoritative prices, approvals, payment success, or invoice issuance.
