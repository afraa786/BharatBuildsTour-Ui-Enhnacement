# Phase 1 schema mapping

This document maps the frozen decisions in [contracts.md](contracts.md) to the
PostgreSQL schema introduced by Alembic revision `0002_commercial_schema`. It
is an implementation map, not a new product contract.

| Contract concept | Table(s) | Key persistence and integrity |
| --- | --- | --- |
| Business scope | `businesses` and `business_id` on every commercial table | UUID business identity; tenant-crossing child references use composite FKs where a child also carries a domain ID. Currency is constrained to the contracted MVP value, `INR`. |
| Minimal buyer identity | `buyers` | UUID buyer ID, mutable contact/legal details, and a check requiring a display name or WhatsApp contact. A business-scoped composite key supports safe quote FKs. |
| Catalog truth | `products` | Business-scoped SKU and normalized-SKU uniqueness; exact BIGINT paise cost/base price; GST basis points; explicit stock/sellable units and `NUMERIC(18,3)` pack size. |
| Exact aliases | `product_aliases` | Duplicate alias-to-product rows are blocked, while the same normalized alias may map to multiple products as required for `AMBIGUOUS` results. |
| Substitutes | `product_substitutes` | Same-business product/substitute FKs, unique directed pair, positive rank, and no self-substitution. Substitutes remain separate from exact matching. |
| Inventory truth | `inventory`, `stock_movements` | One inventory row per business/product, non-negative `NUMERIC(18,3)` on-hand quantity, optional reorder threshold, optimistic row version, and unique movement key. There is no reservation column. |
| Pricing policy | `pricing_rules` | Versioned demo/business rules with basis-point checks, effective range, and at most one row marked active per business. Numeric policy values are data, not schema defaults. |
| Rehbar run linkage | `quote_lineages` | One lockable lineage row per `(business_id, run_id)`; no Fareed-owned workflow/run table. |
| Immutable quote versions | `quotes`, `quote_items` | UUID per version; unique run/version; one current version per run; exact status vocabulary; BIGINT paise totals with sum checks; JSONB buyer/policy/tax evidence snapshots; exact pricing-rule version and same-business product FKs. |
| Approval and acceptance evidence | `quotes` | Opaque, business-scoped unique evidence IDs and JSONB evidence, separate policy result/evidence flags, and checks preventing an accepted quote without issuance time and timestamped acceptance evidence. |
| Payment intent/truth | `payments` | Exact quote version/run FK, BIGINT paise and INR checks, contracted state vocabulary with paid/pending evidence checks, provider IDs kept separate, unique provider reference/link/payment IDs, and at most one created/pending/paid row per quote version. |
| Provider event replay | `payment_events` | Verified event metadata only; unique `(provider, provider_account_key, provider_event_id)`; same-business payment/provider-account FK. |
| Durable handoff | `payment_outbox` | One topic record per verified event, with an index restricted to unpublished rows. No message transport is implemented in Phase 1. |
| Invoice numbering | `invoice_sequences` | Lockable counter per business/calendar year. It supports `INV-YYYY-NNNNNN`; allocation logic remains Phase 5. |
| Invoice identity/snapshot | `invoices` | Unique business/payment, business/quote, and business/invoice number; exact quote/payment/run FKs; immutable JSONB snapshot; BIGINT paise total; pending/generated artifact states. |
| Mutation idempotency | `idempotency_keys` | Unique `(business_id, action, key)`, SHA-256 request fingerprint, processing/completed state, safe response reference, and optional retention expiry. |

## Index rationale

- Product names and aliases lead with `business_id` because every catalog lookup
  is tenant-scoped. SKU uses a uniqueness constraint, which also provides its
  lookup index.
- Quote status and expiry have separate business-leading indexes because queues
  and expiry processing filter them independently. A partial unique index allows
  only one `is_current` quote per business/run while retaining history.
- Payments have a business/quote/version index for quote-to-payment reads. The
  partial unique index covers only `CREATED`, `PENDING`, and `PAID`, so
  failed/cancelled/expired attempts can remain as history.
- Provider event uniqueness follows the provider-account scope from the contract,
  while a separate business/payment index supports payment timelines.
- Invoice uniqueness constraints provide the payment and number access paths, so
  redundant standalone indexes are intentionally omitted.
- The outbox index contains only unpublished rows, keeping the future dispatch
  scan small.
- Idempotency scope/key and inventory business/product are already backed by
  unique/primary-key indexes; no duplicate indexes are added.

All financial and historical foreign keys use `ON DELETE RESTRICT`. Phase 1
does not add HTTP APIs, provider integrations, invoice/PDF generation,
authentication, or workflow state.
