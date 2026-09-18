# StockAware Phase 6 — Backend Integration and Acceptance

## Status and authority

The PostgreSQL-backed **demo commercial journey** is exercised end to end
with a fake Razorpay adapter: seeded catalog → exact match → read-only stock
check → frozen quote → trusted owner approval evidence → trusted buyer
acceptance evidence → payment-link intent → signed paid webhook → durable
outbox → verified-payment demo invoice → PDF artifact. This document is an
integration record, not a live release approval. [Backend contracts](contracts.md)
remain authoritative; the original [build plan](build-plan.md) owns product
scope. No commercial schema migration was added after Phase 1.

## Ownership and stable handoff IDs

Rehbar owns WhatsApp ingress, run lifecycle, admin command/owner evidence,
and buyer acceptance provenance. Fareed owns product/SKU, inventory, pricing,
quote arithmetic/snapshots, Razorpay payment truth, and invoice/artifact
truth. Yunus consumes safe API data in Next.js without calculating money or
marking payment paid. Amir owns fixtures and acceptance scenarios.

`business_id` is the authorization scope; `run_id` is Rehbar's opaque
correlation ID. Fareed's version-specific `quote_id` and positive
`quote_version` are stable through approval, acceptance, payment, and invoice.
`payment_id`/`invoice_id` are local UUIDs; Razorpay link/payment/event IDs are
separate provider strings. Neither Rehbar status nor a buyer redirect
substitutes for a signed provider event.

Approval/acceptance application remains an **internal service boundary** in
`server/app/modules/pricing/evidence.py`. Its exact authenticated transport
from Rehbar is not frozen; Phase 6 tests invoke it with explicit trusted
actor/message evidence. No browser-callable “approve” or “accept” endpoint was
invented. The existing Rehbar `/runs/*`, `/admin/command`, and WhatsApp routes
were inspected and not rewritten. Their authentication and shared error
envelope must be separately audited by that owner before live deployment.

## Fareed API inventory

| Phase | Method/path | Response/state purpose |
| --- | --- | --- |
| 2 | `GET /products` | Business-scoped safe product list. |
| 2 | `POST /catalog/match` | `MATCHED`, `AMBIGUOUS`, or `NOT_FOUND`; no SKU selected for ambiguity. |
| 2 | `POST /inventory/check` | Decimal stock-unit quantities, shortage/low-stock and substitutes; no reservation. |
| 3 | `POST /pricing/quote` | New version-specific UUID, `DRAFT`/`GENERATED`, exact INR paise totals and approval reasons. |
| 4 | `POST /payments/create-link` | Accepted-quote `CREATED` intent then `PENDING` Razorpay link; idempotent reference. |
| 4 | `POST /payments/webhook` | Raw-body HMAC-verified, full captured `PAID` transition and outbox. |
| 4 | `GET /payments/{payment_id}` | Safe business-scoped payment status. |
| 5 | `POST /invoice/generate` | Verified-payment demo invoice, retry-safe artifact lifecycle. |
| 5 | `GET /invoices/{invoice_id}` | Immutable number/status/amount and guarded download availability. |
| 5 | `GET /invoices/{invoice_id}/artifact` | Internal-authenticated, checksum-verified PDF. |

Commercial routes use the canonical `{ "error": { "code", "message",
"request_id", "details?" } }` envelope, including framework validation
errors. Internal routes require `X-Internal-Service-Token` mapped to a
configured business; mutation routes require `Idempotency-Key`. The public
Razorpay webhook uses exact raw-body HMAC instead. Responses expose stable
UUIDs, UTC timestamps, INR integer paise, decimal-string quantities, explicit
quote/payment/invoice state strings, and nullable artifact URL until ready.
Internal-only authentication must not be embedded in Yunus's browser bundle;
a separate constrained buyer capability is deferred.

## Acceptance evidence and payment state

The demo seed's owner-all-quote policy produces a `DRAFT`; trusted owner
evidence moves the exact current version to `GENERATED`, and trusted buyer
WhatsApp evidence moves it to `ACCEPTED`. Payment link creation rechecks
version, acceptance, approval, expiry, amount/currency, and stock. No stock is
reserved or deducted. The link intent is committed before the provider call;
provider I/O runs outside a DB transaction. Its unique reference is the
local payment UUID. Ambiguous provider outcomes remain `CREATED` and block
blind retries pending reconciliation.

Signed full-paid events verify account, link/reference, amount paid, currency,
and captured status before `PAID`. Provider event ID and payload hash make
exact replay a no-op; conflicting replay is `DUPLICATE_EVENT`. Signed
mismatches and extra captured payments produce reconciliation outbox records.
A legitimate late payment remains `PAID` with `reconciliation_hold`, which
blocks automatic invoicing. The `payment.verified`/reconciliation outbox is
committed with payment/event state, but transport to Rehbar is **deferred**.
`FAILED`, `EXPIRED`, and `CANCELLED` exist in the frozen state model; their
provider-confirmed operational adapters and uncertain-reference reconciliation
are not yet implemented. Do not treat this demo as live payment readiness.

## Invoice and artifact state

Only a `PAID` local payment with signed full-payment evidence, exact frozen
quote binding, no hold, and complete demo seller/buyer billing details can
issue a demo document. A non-demo business is blocked pending accounting
approval of GST classification/legal presentation. A transaction locks the
payment, allocates `INV-YYYY-NNNNNN` under a business/year sequence-row lock
in its configured timezone, and commits one immutable
`PENDING_ARTIFACT` invoice. ReportLab renders a clearly marked demo PDF from
the frozen snapshot outside that transaction. Local ignored storage uses
atomic replacement; a second transaction saves SHA-256 and `GENERATED`.
PDF failure/retry uses the same invoice ID/number. This is not a GST tax
invoice or a tax-compliance claim.

## PostgreSQL and acceptance evidence

`server/tests/test_phase6_e2e.py` covers the full fake-provider journey on a
fresh migrated PostgreSQL database, including ambiguity, approval gate,
prepayment invoice rejection, unsigned-webhook rejection, exact replay,
outbox and PDF. `test_phase6_concurrency.py` races duplicate link and webhook
requests on independent PostgreSQL connections; earlier Phase 3/5 tests cover
quote-version and invoice-number races. `test_phase6_invoice_replay.py`
regresses a later hold not changing an already issued invoice's replay.
Phase 2–5 tests additionally cover no-match, shortage, stale/expired quote,
unsafe discount, amount/currency mismatch, partial payment, account/link
mismatch, secret rotation, late hold, PDF failure/retry, business isolation,
and idempotency conflict. Tests use a fake provider: **no live charge**.

Run from repo root:

```bash
make test-pg
make lint
docker compose config --quiet
cd server && .venv/bin/alembic check
```

The independent `scratch/integration_harness/` suite and validator are
read-only QA inputs. Two harness pricing vectors disagree with the frozen
contract (discount clipping and zero-taxable 100% discount); implementation
follows `docs/contracts.md`, and the QA owner must resolve those vectors.

## External and business gates before launch

- Fareed + Rehbar: authenticate the exact approval/acceptance transport and
  consume the outbox with durable idempotent delivery; audit Rehbar route auth.
- Fareed: implement/reference-test provider reconciliation after uncertain
  link creation and provider-confirmed cancel/expire/failure transitions;
  validate test-mode then live merchant configuration without real charges in
  automated tests.
- Business/accounting owner: confirm real SKU/GST inputs, CGST/SGST/IGST,
  place of supply, legally required fields, number format, and PDF layout.
  Non-demo invoice issuance stays blocked until then.
- Fareed + Yunus: replace the single-business internal token with the
  required multi-business/owner/buyer authorization capabilities before
  exposing commercial reads or artifacts to browsers.
- Rehbar + wholesaler: decide stock deduction trigger and paid-shortage
  resolution. Current stock checks never reserve or deduct.
- Deployment owner: decide S3/AWS artifact storage, backup/retention,
  monitoring, HTTPS/webhook configuration, and secret management.

These are known deferred gates, not silent defaults. Independent audit is
required before merging or enabling live payments.
