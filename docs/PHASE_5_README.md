# StockAware Phase 5 — Demo Invoice and PDF Artifact

## Scope and legal gate

Phase 5 adds verified-payment invoice issuance and local PDF artifacts on the
frozen Phase 1 schema. It does not add a tax-law classification or change
commercial tables. `POST /invoice/generate`, `GET /invoices/{invoice_id}`,
and `GET /invoices/{invoice_id}/artifact` are Fareed-owned internal endpoints
guarded by the existing business-scoped service token. They are not
buyer-public URLs.

**Only explicitly identified demo businesses can generate a PDF in this
checkpoint.** A non-demo business receives `INVOICE_TAX_CONTEXT_REQUIRED`
until the business/accounting owner confirms CGST/SGST/IGST classification,
place of supply, legal fields, number format, and tax-invoice presentation.
Even a demo needs explicit seller legal name/address and frozen buyer legal
name/address; the seed intentionally does not fabricate them. The PDF is
watermarked “DEMO ONLY - not a legally validated GST tax invoice.” This is
not production invoicing authorization.

## API and prerequisites

`POST /invoice/generate` requires `X-Internal-Service-Token`,
`Idempotency-Key`, and `business_id`, stable `run_id`, exact `quote_id` and
`quote_version`, and local `payment_id`. The service locks the business-scoped
payment and requires `PAID`, a provider payment ID/time, signed full-payment
event evidence, no `reconciliation_hold`, and exact quote amount/currency.
The quote must still be the accepted current version. A fresh stock check
blocks automatic issuance if the paid order now needs owner stock resolution.
An unpaid browser redirect or WhatsApp text cannot satisfy these checks.

Response contains immutable `invoice_id`, `invoice_number`, exact linkage,
status, INR paise total and issuance time. `artifact_sha256` and guarded
`download_url` are populated only when status is `GENERATED`. Reads are
business scoped; cross-business IDs return `NOT_FOUND`. The artifact endpoint
verifies its stored SHA-256 before returning a PDF.

## Numbering, snapshot and transaction pattern

Numbers use `INV-YYYY-NNNNNN`, allocated under a PostgreSQL row lock on
`invoice_sequences` for the business and calendar year in its configured
timezone. The transaction first claims the scoped idempotency key and locks
the payment, then checks the quote and legal/demo gates, allocates the number,
and inserts one `PENDING_ARTIFACT` invoice with its frozen snapshot. The
number allocation, invoice row, and idempotency result commit together.
Database uniqueness enforces one invoice per payment, one per quote version,
and one business/number pair. Concurrent same-payment requests reuse the
winner; a different payment for an already invoiced quote needs reconciliation.

The frozen snapshot comes only from quote, quote items, their saved buyer/tax
context, business-approved seller details, and verified payment reference.
It includes SKU/name/unit/quantity, price/discount/tax amounts and totals;
it omits cost, margin, and owner policy. Later live Product or PricingRule
edits do not change the document. The generic quote tax snapshot is retained
but not falsely presented as a legally classified tax invoice.

After the DB commit, a ReportLab PDF is rendered from that snapshot and
atomically written to ignored local storage under `ARTIFACT_DIR`. Docker
persists this path in the `invoice_artifacts` named volume. A second DB
transaction saves an opaque artifact key, checksum, generation time, and
`GENERATED` status. There is **no database lock held during PDF I/O**.

If rendering/writing fails, the committed invoice remains `PENDING_ARTIFACT`.
The caller receives `ARTIFACT_GENERATION_FAILED` (503); retrying the same or
a new idempotency key for the same payment uses the **same invoice ID and
number** and resumes artifact generation. It never consumes another number.
The local storage key is not accepted from callers, and `artifacts/` is
Git-ignored. PDF generation is deterministic for the same snapshot. Demo
rendering currently uses ReportLab's built-in font; Unicode/vernacular font
requirements need design before customer-facing documents.

## Team handoffs and verification

Rehbar must request issuance only after Fareed's verified-payment outbox
event, and must pause when `reconciliation_hold` is true. Rehbar still owns
run lifecycle; invoice rows do not advance it automatically. Yunus should
display the returned invoice number/status and only offer a download after
`GENERATED` under an appropriate authenticated proxy/capability. The current
service token must never be embedded in browser code. Amir can use the
demo-only seed plus explicit test billing data; no production customer data
is seeded.

PostgreSQL tests cover unpaid/held/mismatched payments, signed-event
prerequisite, sequence-year/business isolation, concurrent duplicate
issuance, frozen product snapshot, PDF checksum/download, failure/retry, and
cross-business reads. Run `make test-pg`, Ruff, Compose validation, and
Alembic drift check. No live tax invoice or AWS artifact verification was
performed.
