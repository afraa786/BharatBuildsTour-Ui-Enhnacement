# StockAware Backend Contracts

## 1. Contract Status

**Status:** Contract v1, frozen for the current single-wholesaler MVP and Phase 1 schema work. This document is the authoritative backend interface and invariant contract. [The build plan](build-plan.md) and [Phase 0 implementation plan](backend-implementation-plan.md) provide product scope and sequencing; their example payloads are illustrative where this document makes a narrower implementation decision. Changes to a frozen field, state, or formula require an explicit contract revision before dependent code changes. Rehbar and Yunus have not yet acknowledged this document; their integration should use these IDs and payloads or request a revision.

**Notation:** **Requirement** means the supplied StockAware plan explicitly calls for it. **Decision** means the smallest MVP choice made here to make implementation deterministic. **Deferred** means the choice is outside the current contract or needs business/provider confirmation before that later feature is enabled. No commercial schema, API, or migration exists yet.

**Scope assumptions (Decision):** The first deployment serves one wholesaler and one owner, but every commercial row is business-scoped so a second wholesaler cannot be mixed into the first one's data. The local system of record is PostgreSQL. All stored timestamps are timezone-aware UTC; the UI may render them in the business's timezone. The master plan's AWS/DynamoDB sketch is a future option, not a change to this PostgreSQL contract. The FastAPI health routes, SQLAlchemy base/session, and empty Alembic baseline are the only backend implementation today.

**Identifier types (Decision):** Fareed-issued entity IDs, including `business_id`, `buyer_id`, `product_id`, `quote_id`, `payment_id`, and `invoice_id`, are UUIDs exposed as canonical strings. Rehbar-issued `run_id`, `approval_id`, `action_id`, and `acceptance_id`, and all Razorpay IDs, are opaque strings; no service parses another owner's ID for meaning.

## 2. System Ownership Boundaries

| Owner | Authoritative state and action | Contract with others |
| --- | --- | --- |
| Rehbar | WhatsApp ingress, message deduplication, `run_id`, Manager/run lifecycle, owner approval and buyer acceptance events, audit timeline, admin commands. | Sends scoped, normalized RFQ and immutable approval/acceptance evidence to Fareed; records Fareed's returned commercial IDs/states in the run. |
| Fareed backend | Business/customer commercial identity, product/SKU and stock truth, pricing rule and quote snapshot, Razorpay link/payment truth, invoice identity and artifact reference. | Returns deterministic match/stock/quote/payment/invoice results. Does not mutate Rehbar's run lifecycle or invent approval. |
| Yunus | Next.js onboarding, admin control room, inventory management UI, buyer quote/payment/invoice pages. | Displays backend amounts and states; does not calculate authoritative totals, approve, mark paid, or issue invoices. |
| Amir | Seed fixtures, QA scenarios, alerts/reminders, summaries, and demo support. | Supplies clearly demo-labeled catalog and edge cases; does not decide hidden commercial policy. |

**Requirement:** The workflow remains WhatsApp → quote → approval if required → buyer acceptance → payment → verified payment → invoice, with auditable handoffs. Rehbar's run states such as `QUOTE_SENT`, `PAYMENT_CONFIRMED`, and `ORDER_CONFIRMED` are not quote or payment row states. `business_id`, `run_id`, version-specific `quote_id`, local `payment_id`, and `invoice_id` must be passed unchanged between systems. Provider IDs are separate fields.

## 3. Identity and Tenancy

### run_id

**Decision:** One `run_id` identifies one buyer RFQ/order inquiry moving through Rehbar's quote-to-cash workflow. Rehbar creates it once when deduplicated intake becomes a run, owns the run record, and sends the same opaque non-empty string on retries and all later handoffs. It may look like `RFQ-1042`, but no backend code parses that format. Its uniqueness scope is `(business_id, run_id)`.

Fareed stores `run_id NOT NULL` on every quote version, payment, and invoice, with a business-scoped index; it is an external reference to Rehbar's run, not a foreign key to a Fareed-owned run table. RFQ-driven catalog/stock requests also require it; generic admin product/stock reads need `business_id` but no run. Products, stock, and pricing rules do not carry a run ID. A run has one quote lineage for the MVP and may have multiple immutable quote versions. `run_id` alone is **not** an idempotency key: one run can legitimately create a new quote version or perform different actions. Rehbar deduplicates inbound WhatsApp message IDs; Fareed deduplicates each commercial mutation separately.

### business_id

**Decision:** `business_id` is an immutable opaque UUID created with the business profile by Fareed's persistence layer during onboarding. It is mandatory and non-null on every commercial record: minimal buyer identity, products, aliases, substitutes, inventory, pricing rules, quotes and lines, payments and provider events, invoices and artifact references, and idempotency records. Every unique key and lookup is scoped by business; SKU uniqueness is `(business_id, sku)`, while alias uniqueness is `(business_id, normalized_alias, product_id)` so one alias can legitimately be ambiguous. Child tables use a business-scoped FK/composite FK or equivalent checked relationship to prevent a row for business A referencing business B. Indexes for commercial lookups start with `business_id` where useful.

`business_id` in a request is a lookup claim, not authorization. A trusted caller identity must be mapped to allowed business IDs server-side; every repository query and mutation filters by the authorized business. Requests for another business's IDs return `NOT_FOUND` without leaking that record. The public webhook derives business scope from the verified provider account/link association, never from an untrusted JSON `business_id`. Authentication needed to enforce this is a dependency before exposing commercial routes; it is not implemented today.

### buyer/customer identity

**Decision:** A minimal business-scoped `buyer_id` identifies the customer for quotes; Fareed creates it as an opaque UUID in a small buyer/contact record. This is identity storage, not a CRM. A quote requires `business_id`, `run_id`, `buyer_id`, and at least one reachable buyer contact or display label. For the WhatsApp MVP, the normalized E.164 WhatsApp number supplied by Rehbar is the reachable contact; it is **not** the primary key and is not globally unique. Name, phone, company/legal name, billing address, and GSTIN may be corrected over time, so every issued quote stores the buyer display/contact snapshot used when issued. Invoice issuance additionally requires the business-approved seller and buyer billing details appropriate to the invoice type.

If a WhatsApp number is present but the buyer name is unknown, create/resolve the minimal buyer record and show an explicit `buyer_name_missing`/clarification state; do not invent a legal name. If `buyer_id` is absent, or both reachable contact and display label are absent, quote generation is blocked for clarification. Sending the quote and recording acceptance still require a verifiable buyer channel/actor. No customer tier, credit balance, marketing list, or CRM history is part of this MVP contract.

`buyer_name_missing` is a clarification flag/reason for Rehbar, not an additional quote status. It cannot be promoted into a fabricated legal buyer name on an invoice.

### approval identity

**Requirement:** Approvals bind to exact run/action/version and an authorized actor. **Decision:** Rehbar is the source of truth for owner approval and generates a stable `approval_id` plus `action_id`. Its evidence includes `business_id`, `run_id`, `quote_id`, `quote_version`, approving actor ID, decision, timestamp, and expiry/revocation if set. Only the business's configured owner/admin actor may approve; no elaborate RBAC is introduced. Fareed stores the approval reference and the verified binding on the quote/version or payment action, and accepts it only through a trusted Rehbar service call or an independently verified Rehbar record. A client-supplied `approved: true` is never sufficient. Missing, rejected, revoked, expired, wrong-business, wrong-action, or stale-version approval blocks the action. When policy does not require approval, `approval_id` is null and the policy snapshot records why.

## 4. Catalog Contract

**Requirement:** Match informal names to real SKUs; never invent an SKU. **Decision:** Match only active products in the authorized business. Normalize case, surrounding/internal whitespace, and harmless punctuation for lookup; retain the original text. An exact normalized SKU, product name, or declared alias can produce a match. No fuzzy candidate is automatically promoted to a sellable SKU in MVP.

| Result | Exact meaning | Required response data |
| --- | --- | --- |
| `MATCHED` | Exactly one active product matches the normalized SKU/name/alias and requested unit can be interpreted. | Original request, product ID, SKU, canonical name, sellable unit/pack, match source, candidate list with one item. |
| `AMBIGUOUS` | More than one eligible product matches, or the unit/pack meaning is unresolved. | Original request, candidate IDs/SKUs and reasons; **no selected SKU**. Rehbar asks for clarification. |
| `NOT_FOUND` | No eligible exact match exists. | Original request and empty selected SKU; optional search suggestions clearly marked non-sellable. |

Aliases participate in exact matching and may map to multiple products. Substitutes **do not** participate in exact matching: they are separate, explicit suggestions after a known SKU is unavailable or requested by the buyer. A substitute has its own SKU, stock, price, and required buyer/owner confirmation before replacing a line. `AMBIGUOUS` and `NOT_FOUND` are normal 200 match results; attempts to price without a resolved SKU fail with the error codes in section 12. Product cost, margin floor, and internal pricing policy never appear in buyer responses.

## 5. Inventory Contract

**Requirement:** Inventory truth is on the admin side; quote preparation may read stock and must not hard-deduct it by default. **Decision:** Phase 1 stores `on_hand_qty` in the product's canonical stock unit and a row version. No reservation balance is introduced for the MVP. `sellable_qty = max(on_hand_qty, 0)` and `available_qty` means that same current unreserved quantity at the read timestamp. Quantities use a decimal representation with at most three fractional places; products marked indivisible reject fractional requests. Pack/unit conversion must use explicit product metadata, never a guessed conversion.

`POST /inventory/check` returns the requested normalized quantity, stock unit, on-hand/sellable quantity, `checked_at`, and one of `AVAILABLE`, `LOW_STOCK`, `INSUFFICIENT_STOCK`, or `OUT_OF_STOCK`. `LOW_STOCK` means the request is currently fulfillable but the resulting balance would be at or below that product's configured reorder threshold; absent threshold means no low-stock flag. Insufficient/out-of-stock results contain only eligible, separately identified substitute suggestions and do not change the quote line automatically. A quote check is a point-in-time observation, not a promise of future stock.

Status precedence for a positive requested quantity is `OUT_OF_STOCK` when sellable quantity is zero, then `INSUFFICIENT_STOCK` when it is below the request, then `LOW_STOCK` when the request can be met but crosses the threshold, otherwise `AVAILABLE`. A zero or negative request is invalid input, not a stock status.

Before a payment link is created, stock is checked again; if insufficient, block the link and return `INSUFFICIENT_STOCK`. This recheck still does not reserve stock. A later stock mutation/deduction must atomically check the row version/quantity, write a uniquely keyed stock movement, and never make stock negative; concurrent winners/losers receive deterministic results. **Deferred:** the business and Rehbar must choose the actual deduction trigger at approved order versus verified payment before enabling order confirmation. Phase 1 needs no reservation field or automatic deduction. If a buyer pays after stock becomes insufficient, payment remains truthfully `PAID`; automatic invoice/order confirmation pauses for owner resolution rather than pretending payment failed.

## 6. Pricing Contract

**Requirement:** Apply cost/selling prices, discount cap, margin floor, quote totals, and GST-ready tax output; flag exceptions for owner approval. **Decision:** The MVP uses each product's tax-exclusive base selling price per sellable unit and one active business-level pricing rule. Customer tiers, product-specific overrides, fixed-amount discounts, and promotion stacking are deferred. If no active rule exists, or more than one rule is active for the same business/time, quote creation fails rather than selecting an arbitrary rule. The rule records a business-configured maximum discount in basis points and minimum gross margin in basis points; this document sets **no numeric defaults**. An owner setting may require approval for all quotes; absent approval preferences fail closed as approval required.

**Money policy (Decision):** Currency is `INR` for this MVP. PostgreSQL stores all money amounts as signed `BIGINT` integer paise; API fields use explicit `*_paise` integer names plus `currency: "INR"`. Python uses integer paise and `Decimal` for multiplication/division; binary floating-point is forbidden. Discount and tax rates are integer basis points (`10000` = 100%). Product quantity is a decimal value in the declared sellable unit. The calculation order for each quote line is:

1. `gross_paise = ROUND_HALF_UP(unit_price_paise × quantity)` to one paise.
2. `discount_paise = ROUND_HALF_UP(gross_paise × discount_bps / 10000)`; discount is 0..gross.
3. `taxable_paise = gross_paise - discount_paise`.
4. `tax_paise = ROUND_HALF_UP(taxable_paise × gst_rate_bps / 10000)`.
5. `line_total_paise = taxable_paise + tax_paise`. Quote subtotal is the sum of line taxable amounts; quote tax is the sum of rounded line taxes; payable total is subtotal + tax. No quote-level re-rounding or hidden fees are allowed.

Quantities travel through JSON as decimal strings (for example, `"2.500"`), not floating-point numbers; rates travel as integer basis points. Pricing rule priority is intentionally singular: exactly one active business rule applies at quote time, with no implicit customer/product override.

For margin policy, compare tax-exclusive net revenue (`taxable_paise`) with `ROUND_HALF_UP(cost_unit_paise × quantity)` per line. Gross margin is `(net revenue - cost) / net revenue`; compare by integer cross-multiplication against the rule's floor to avoid a rounded percentage deciding approval. Zero/negative net revenue is invalid, not approvable. A requested discount above cap **or** margin below floor returns a priced draft with `approval_required: true` and explicit reason codes; it is not silently clipped. Rehbar must obtain owner approval for that exact quote version before Fareed marks it generated/sellable. Owner rejection cancels the draft. The rule ID/version, cost, base price, discount, tax rate, all intermediate paise amounts, and reason codes are captured in the quote snapshot; later catalog/rule edits cannot change it.

`approval_required` is the frozen policy result, not proof that approval occurred. A separate `approval_satisfied` result becomes true only when Fareed validates exact-version Rehbar evidence; `DRAFT → GENERATED` requires it when approval was required.

**GST/tax policy (Decision):** Every product carries an explicitly configured GST rate in basis points; no tax rate is guessed from its name or silently defaulted to 18%. Tax is computed per line as above. The issued quote stores the rate, taxable value, tax amount, and seller/buyer tax context snapshot. A rate change affects only new quote versions. **Deferred:** CGST/SGST versus IGST classification, place-of-supply inputs, tax invoice layout, and any legally required rounding/display rules must be confirmed with the business/accounting owner before issuing a real tax invoice. If required tax context is missing, the tax invoice is blocked rather than fabricated. This tax calculation contract is an MVP commercial arithmetic choice, not tax advice.

## 7. Quote Contract

### lifecycle

**Decision:** Quote row status is exactly `DRAFT`, `GENERATED`, `ACCEPTED`, `EXPIRED`, or `CANCELLED`. A quote begins as a saved `DRAFT`; `GENERATED` means its immutable commercial artifact is ready after any required owner approval. Rehbar separately records `QUOTE_SENT`. Only a `GENERATED` quote may be accepted. `GENERATED` may become `ACCEPTED`, `EXPIRED` (before acceptance), or `CANCELLED` (owner withdrawal/supersession before payment). `DRAFT` may become `GENERATED` or `CANCELLED`; an unapproved/rejected draft is cancelled. `ACCEPTED` stays accepted while payment is pending, paid, failed, or expired; payment is tracked on the payment row. An accepted quote can be cancelled only if no verified payment exists and any live provider link has been confirmed cancelled. There is no quote `PAID`, `COMPLETED`, or `REJECTED` state. Rehbar's run may use `REJECTED`, `PAYMENT_CONFIRMED`, and `ORDER_CONFIRMED` independently.

### versioning

**Decision:** Every persisted priced draft is an immutable commercial version: editing any line, quantity, SKU, price, discount, tax input, buyer billing data, or expiry creates a new version. `run_id` is the stable lineage; `quote_version` is a positive integer increasing within `(business_id, run_id)`. `quote_id` is a UUID for **one version**, changes on revision, and is never reused; `Q-1042-V1` may be a display label derived from run/version but is not the database/API ID. `(business_id, run_id, quote_version)` and `(business_id, quote_id)` are unique. Rehbar's run points to the latest active `quote_id`/version.

Creating a new version atomically supersedes/cancels the prior unpaid version. If that version has a live payment link, first request and confirm provider cancellation **outside** the database transaction; until then, the old version remains active and a new version is not activated. The version-creation transaction then rechecks the local payment state under lock. A late verified paid event still records payment truth and moves the run to manual reconciliation rather than silently issuing an invoice for the replacement version. A paid version cannot be repriced; use a separate adjustment/refund process later. Acceptance, approval, and payment creation must compare the exact `quote_id` **and** `quote_version` to the latest active version under lock. Old versions return `QUOTE_VERSION_MISMATCH` even if their IDs still exist. Payment and invoice records reference the exact version-specific `quote_id`.

### acceptance

**Requirement:** Buyer acceptance precedes payment link creation and is distinct from owner approval. **Decision:** Rehbar is the acceptance source of truth. It records `acceptance_id`, `business_id`, `run_id`, exact `quote_id`/version, buyer actor or verified WhatsApp contact, timestamp, channel (`whatsapp` or authenticated quote page), and immutable source message ID/page action reference. Fareed stores a reference and verified binding; a bare `accepted: true` from a browser or model is insufficient. A duplicate acceptance of the same version is idempotent; acceptance of a superseded/expired version is rejected. Approval is by the business owner/admin for a policy exception; acceptance is by the buyer for the commercial offer. They cannot substitute for each other.

Fareed applies validated acceptance evidence to move `GENERATED → ACCEPTED` before creating a link. A trusted Rehbar handoff may supply that evidence with `POST /payments/create-link`; a failed provider call leaves the quote accepted and the same local payment intent safely retryable. Approval evidence is applied before issuance; its transport may be a trusted internal command or event, but the frozen evidence fields and version checks are identical.

### snapshots

**Requirement:** Totals must be reproducible from stored inputs. **Decision:** The version snapshot contains business/run/buyer IDs and buyer display snapshot; SKU/product name/unit/quantity; cost and base unit price; discount rate/amount; taxable amount; GST rate/amount; payable line/quote totals; currency; pricing rule ID/version and policy reasons; tax context; creation/expiry times. Financial fields never mutate after the draft is saved. Store exact inputs and intermediate rounded paise values. Public quote output omits cost and private rules. A PDF/page renders the stored snapshot rather than recalculating from live products.

### expiry

**Decision:** Each quote version has a UTC `expires_at` set from an explicit business-configured validity period; no unconfigured default duration is invented. `DRAFT` cannot be accepted. A `GENERATED` quote is eligible for acceptance only while `now < expires_at`; every action checks this directly even if a background expiry job has not run. Unaccepted generated quotes may transition to `EXPIRED`. An already `ACCEPTED` quote retains that status; its payment link expires no later than the quote's `expires_at`, and no new link is created once that instant passes. A delayed verified provider payment is assessed by provider payment time and link/quote binding; webhook arrival time alone does not invalidate a real payment. Any verified payment after allowed expiry is recorded as paid but held for owner reconciliation, not silently invoiced.

## 8. Payment Contract

**Requirement:** Razorpay link from an accepted quote, provider-verified payment, idempotent callbacks, no success from buyer text. **Decision:** One active local payment attempt/link is allowed per quote version. `payment_id` is the local opaque ID; `provider_link_id`, `provider_payment_id`, and optional provider order ID are separate fields. The payment row stores `business_id`, `run_id`, exact `quote_id`/version, `amount_paise`, `currency`, link expiry, and provider IDs. It never takes an amount from the browser; its amount equals the stored quote payable total exactly.

Local states are `CREATED` (intent persisted, provider result not yet confirmed), `PENDING` (link issued), `PAID` (full amount verified from Razorpay), `FAILED` (confirmed unrecoverable link creation/final failure), `EXPIRED`, and `CANCELLED`. Normal transitions are `CREATED → PENDING|FAILED`, then `PENDING → PAID|EXPIRED|CANCELLED`. A failed individual payment attempt on an otherwise payable link is an event, not a terminal `FAILED` link. `PAID` is not reverted to `FAILED`; refunds, chargebacks, and partial payments are outside the MVP state machine and require a separate future record/contract. A verified late or out-of-order paid event is still recorded as payment truth even if a local expiry/cancel state was observed; automatic invoice/order progression pauses for reconciliation if validity is disputed.

The exceptional `EXPIRED|CANCELLED → PAID` transition is permitted only on verified provider evidence and sets a reconciliation hold; it never auto-issues an invoice. A terminal `FAILED` link-creation intent cannot be reused for a new link without reconciling the provider reference first.

Only a correctly signed provider webhook representing full paid status, or an authenticated server-to-server Razorpay status fetch with the same link/amount/currency, may establish `PAID`. Buyer text, frontend redirect, an unsigned callback, `payment.authorized`, and a client-supplied status cannot. The provider's payment truth and Rehbar's run status are distinct: Fareed emits a durable verified-payment result after commit; Rehbar may then advance the run.

## 9. Razorpay Webhook Contract

**Decision:** Use one Razorpay Standard Payment Link per payable quote version for the MVP; no separate Orders API is required. Create it with exact quote `amount_paise`, `currency: INR`, `accept_partial: false`, `expire_by` no later than quote expiry, and a unique `reference_id` derived from the persisted local payment ID (within Razorpay's length limit). Save the provider link ID and URL against the same business/quote/payment. Reusing an idempotency key returns the same link; a second active link for the version is forbidden. If the provider call times out, reconcile using the reference ID before retrying, rather than blindly creating another link. Razorpay documents minor-unit amounts, unique `reference_id`, partial-payment settings, and link states in its [Payment Links API](https://razorpay.com/docs/api/payments/payment-links/) and [link state guide](https://razorpay.com/docs/payments/payment-links/states/).

**Requirement and provider rule:** `POST /payments/webhook` reads the **raw request bytes**. Before JSON parsing or DB mutation, verify `X-Razorpay-Signature` with the configured webhook secret using constant-time comparison. Razorpay documents HMAC-SHA256 over the raw body, `x-razorpay-event-id` for deduplication, and unordered delivery in its [webhook validation guide](https://razorpay.com/docs/webhooks/validate-test/). Do not treat a browser callback as equivalent to a verified webhook.

After signature verification, require a non-empty provider event ID, expected event type (paid link or equivalent confirmed full payment), known `provider_link_id`/reference ID, matching provider account/business, exact `amount_paise`, `amount_paid_paise == amount_paise`, `currency`, and a captured/paid provider state. Store the event ID and a safe payload hash under a unique provider/account key. A valid exact replay returns HTTP 200 with `duplicate: true` and performs no second transition/side effect. The same event ID with different signed content is a `DUPLICATE_EVENT` conflict for investigation. An invalid signature is rejected before event insertion. A signed amount mismatch is quarantined/alerted and never marks payment paid; once safely recorded it may be acknowledged with 2xx to avoid useless provider retries. Provider events that arrive out of order never regress `PAID`. The [Razorpay webhook FAQ](https://razorpay.com/docs/webhooks/faqs/) describes at-least-once delivery and retries.

Webhook processing commits the unique event receipt, legal payment transition, and a durable downstream notification/outbox record in one transaction. Invoice generation is a separate idempotent action after verified payment. Raw signed payloads, secrets, and buyer financial details are not logged. Secret rotation must allow verification of already retried events with the prior secret during a controlled overlap, as described in Razorpay's validation guide.

## 10. Invoice Contract

**Requirement:** Invoice generation needs a valid verified payment trigger; duplicates must not issue duplicates. **Decision:** `POST /invoice/generate` requires `business_id`, local `payment_id` in `PAID`, the exact linked accepted quote version, and complete business-approved seller/buyer invoice details. It checks the payment amount/currency against the frozen quote and ensures no disputed late/invalid payment or paid-after-stock-shortage hold is being auto-processed. An unpaid, mismatched, or unverified payment cannot create an invoice. Invoice records carry `business_id`, `run_id`, version-specific `quote_id`, `payment_id`, immutable buyer/seller/item/tax/total snapshots, `invoice_id`, `invoice_number`, issuance time, and artifact reference. `(business_id, payment_id)` and `(business_id, invoice_number)` are unique.

Also enforce unique `(business_id, quote_id)`: the MVP issues at most one invoice per exact quote version. If an accidental second provider payment is verified for that version, record it as paid truth but hold it for overpayment resolution; never issue a second invoice automatically.

**Numbering decision:** For the MVP, use `INV-YYYY-NNNNNN`, for example `INV-2026-000001`, with a transactionally allocated sequence per business and calendar year in the business's configured timezone (default `Asia/Kolkata` for the initial Indian wholesaler). A sequence may have gaps after failed issuance; numbers are never reused. The business/accounting owner must confirm that this display format and invoice type meet its real invoicing practice before issuing live tax invoices. The database always stores the number as a business-scoped immutable string; no format is parsed for identity.

Invoice state is `PENDING_ARTIFACT` while the DB issuance/snapshot is committed and the PDF is being written, then `GENERATED` only after the artifact exists. A failed PDF write remains recoverable with the same invoice ID/number. Store the PDF in local artifact storage for the demo, with only an opaque storage key/checksum and access metadata in PostgreSQL; later storage may be S3. Resend/download reads the existing immutable invoice and artifact, never issues a new number. A retry for the same payment returns that invoice. Pro forma documents, credit notes, refunds, and tax filing are deferred.

## 11. Idempotency Contract

**Requirement:** Duplicate approvals, webhooks, links, and invoices must not duplicate commercial actions. **Decision:** Every Fareed-owned mutating client/internal command (`POST /pricing/quote` when it saves a version, `POST /payments/create-link`, `POST /invoice/generate`, later admin stock mutations) requires `Idempotency-Key`. Scope is `(business_id, action/endpoint, key)`; `run_id` and quote version are included in the canonical request fingerprint, not substituted for the key. A key is an opaque caller-generated string reused on retries of the *same intended action*. Rehbar separately applies this rule to its WhatsApp/admin approval and acceptance mutations. Read-only `GET`, catalog match, and stock-check calls do not require a key even when transported as `POST`.

Persist a SHA-256 fingerprint of a canonical validated request plus action scope, processing state, and the final HTTP status/safe response reference. Same key and fingerprint after completion returns the same result without redoing work; same key with different fingerprint returns `IDEMPOTENCY_CONFLICT` (409). A concurrent retry while the first action is processing returns a stable in-progress response with retry guidance; it does not start a second mutation. The uniqueness constraint on `(business_id, action, key)` and the domain rows' unique keys enforce this across workers/restarts. A quote revision is a new action/key and new version. Retention must cover the quote/payment/invoice retry horizon; do not discard keys while the underlying action is still retryable.

The first transaction claims the key and validates preconditions. For a pure DB action, business rows and the completed idempotency result commit together. For an external Razorpay call, persist an intent/reference before the network call, release the DB transaction, then commit the provider result; retries reconcile the intent/provider reference. Webhooks use their verified provider event ID as the unique key rather than a client header. A duplicate webhook's event insert/state change/outbox write must be one transaction.

## 12. Error Contract

**Decision:** All Fareed HTTP errors use this envelope. `request_id` is generated by the API or accepted from a trusted internal caller and appears in logs; `details` is optional safe structured data. Include `run_id` in `details` when known, never secrets, cost, or another business's identifiers.

```json
{
  "error": {
    "code": "QUOTE_VERSION_MISMATCH",
    "message": "The quote version is no longer current.",
    "details": {"run_id": "RFQ-1042", "current_quote_id": "6b530cb4-3510-4b83-9152-d7182b9164d5"},
    "request_id": "req_7a1"
  }
}
```

| Code | HTTP for a failed direct request | Meaning |
| --- | --- | --- |
| `NOT_FOUND` | 404 | No authorized record exists; also used for cross-business ID lookups. |
| `AMBIGUOUS` | 409 | Caller tried to use an unresolved catalog match; match endpoint itself returns a 200 result with `AMBIGUOUS` status. |
| `INSUFFICIENT_STOCK` | 409 | A sale-changing action cannot proceed with current stock; stock-check endpoint may instead return this as a 200 result status. |
| `QUOTE_EXPIRED` | 409 | Acceptance or new link attempted at/after `expires_at`. |
| `QUOTE_VERSION_MISMATCH` | 409 | Superseded/stale quote ID or version. |
| `APPROVAL_REQUIRED` | 409 | Exact-version required approval evidence is absent or invalid; unauthorized actor also gets 403. |
| `PAYMENT_AMOUNT_MISMATCH` | 409 | Direct action/provider reconciliation amount differs from frozen quote; a signed webhook mismatch is quarantined and not marked paid. |
| `INVALID_WEBHOOK_SIGNATURE` | 401 | Razorpay signature missing/invalid. |
| `DUPLICATE_EVENT` | 409 | Same provider event ID with conflicting signed payload; exact replay returns 200 and `duplicate: true`. |
| `IDEMPOTENCY_CONFLICT` | 409 | Same scoped key reused with a different request fingerprint. |

Validation failures use 422 with the same envelope; the implementation must normalize FastAPI's default validation response before commercial APIs are exposed. Unexpected errors use a generic 500 with `request_id` and no stack trace in the response. Rehbar should use the same envelope on its own APIs or adapt at the boundary; error codes above are stable for Yunus's UI.

## 13. Transaction and Concurrency Contract

**Decision:** PostgreSQL is the concurrency authority. In-memory locks/sets are never sufficient. Transactions must include these atomic units:

1. **Quote version creation:** after confirming any prior live provider link is cancelled outside the transaction, claim idempotency key, lock the `(business_id, run_id)` quote lineage (or equivalent unique/version row), recheck that the prior version has not become paid, validate current version and product/rule snapshot, insert the next immutable version, supersede the prior unpaid version, and store the result. Unique `(business_id, run_id, quote_version)` is the final race guard. If provider cancellation is uncertain, do not activate the replacement version; reconcile first.
2. **Quote status/acceptance and approval application:** compare authorized business, exact `quote_id`/version, active status, expiry, and evidence identity under lock before status change. Rehbar owns evidence; Fareed does not accept a bare boolean.
3. **Inventory mutation:** lock/version-check the business/product stock row, ensure non-negative result, write a unique stock movement, and commit together. Quote-time checks are read-only and may become stale; link creation rechecks stock but does not reserve it.
4. **Payment link creation:** atomically claim idempotency and persist one local intent/unique version binding, then call Razorpay **outside** the transaction, then atomically save the provider link/result. Reconcile uncertain provider outcomes by unique reference ID.
5. **Webhook/payment transition:** after signature verification, atomically insert unique event ID, compare provider link/amount/currency, apply only legal monotonic state transition, and enqueue one durable downstream event. Exact duplicates are no-ops. No network call or PDF generation occurs while holding the transaction.
6. **Invoice issuance:** lock verified payment, allocate the business/year number, insert unique `(business_id, payment_id)` invoice snapshot and idempotency result in one transaction. Write PDF after commit and advance artifact status by an idempotent second transaction.

Every mutable operation checks current version, authorized actor/business, expiration, and relevant approval/acceptance evidence. Enforce same-business composite relationships and unique constraints in the DB even when service code already checks them. On a unique-conflict race, re-read the winner and return the documented replay/conflict result; do not retry a non-idempotent external effect blindly.

## 14. API Boundary Contract

**Requirement:** Fareed owns `GET /products`, `POST /catalog/match`, `POST /inventory/check`, `POST /pricing/quote`, `POST /payments/create-link`, `POST /payments/webhook`, `POST /invoice/generate`, `GET /payments/{id}`, and `GET /invoices/{id}` in FastAPI. Rehbar owns `POST /webhook/whatsapp`, `POST /admin/command`, `GET /runs/{id}`, and `GET /runs/{id}/timeline`. Yunus owns Next.js pages; no Next.js API route is authoritative for commercial truth. Amir owns fixtures and QA inputs.

**Decision:** All internal commercial requests carry authorized `business_id`; RFQ/quote/payment/invoice requests also carry stable `run_id` and exact quote/version where applicable. Match/stock responses have explicit statuses and candidates/quantities; quote response has version-specific ID, paise totals, currency, expiry, and approval reasons; payment response has local/provider link IDs, status, exact amount, and safe URL; invoice response has immutable ID/number/status/artifact reference. Rehbar maps these results into its run state and audit timeline. Buyer responses omit cost, margin, owner policy, and unrelated customer data. The provider webhook route has no client auth token; its raw-body signature is its authentication. These are contracts for future implementation, not routes already present.

Minimum stable response keys (additional safe fields may be added without changing these meanings):

| Action | Required response fields |
| --- | --- |
| Catalog match | `status`, `requested_text`, `selected_product_id` / `selected_sku` (both null unless `MATCHED`), `candidates[]`, `reason`. |
| Inventory check | `status`, `product_id`, `requested_qty`, `stock_unit`, `available_qty`, `checked_at`, `substitutes[]`. |
| Price quote | `business_id`, `run_id`, `quote_id`, `quote_version`, `status`, `currency`, `subtotal_paise`, `tax_paise`, `total_paise`, `expires_at`, `approval_required`, `approval_satisfied`, `approval_reasons[]`, buyer-safe `lines[]`. |
| Create link/payment read | `payment_id`, `quote_id`, `quote_version`, `status`, `amount_paise`, `currency`, `provider_link_id`, `payment_url`, `expires_at`; nullable provider fields until `PENDING`. |
| Invoice generation/read | `invoice_id`, `invoice_number`, `payment_id`, `quote_id`, `status`, `currency`, `total_paise`, authorized `download_url` only when the PDF exists. |

## 15. Security Assumptions

**Requirement:** Important mutations check run/action/version, approval when required, authorized actor, expiry, and idempotency. **Decision:** Internal Rehbar calls must present a service identity; owner operations must present an authenticated business-scoped owner/admin identity; buyer pages use a constrained authenticated/signed capability for only their own quote/payment/invoice; public Razorpay webhooks use signature verification plus provider-link lookup. The actual authentication mechanism is **not implemented** and must be in place before Phase 2 commercial endpoints are exposed or Phase 4 payments are enabled. Until then, these paths must remain unavailable outside isolated tests. A request-supplied business or actor ID alone is not trust.

Read APIs and writes enforce business scope in the repository layer and response projection. Secrets stay server-side in ignored `.env` locally and a managed secret store in deployment; no Razorpay key/webhook secret appears in Next.js `NEXT_PUBLIC_*`, logs, PDFs, or errors. Use HTTPS for external callbacks, protect invoice downloads, and avoid logging full webhook bodies or buyer-sensitive fields. CORS is browser isolation, not authentication. The existing health routes do not satisfy this security dependency.

## 16. Open Questions / Deferred Decisions

The following do **not** change frozen Phase 1 identity, money, version, or tenancy fields. They need business/team confirmation before the named feature is enabled:

| Deferred item | Owner and gate | Current safe behavior |
| --- | --- | --- |
| Numeric margin floor, discount cap, quote validity, low-stock thresholds, and whether every quote needs owner approval | First wholesaler + Rehbar/Fareed; before live quoting | No hidden defaults. Missing/overlapping pricing rule blocks quote; missing approval preference requires approval. |
| Specific SKU catalog, aliases, substitute eligibility, pack conversions, and GST rates | Amir fixture proposal + wholesaler verification; before live catalog/quote | No invented SKU, unit, stock, or rate. Demo fixtures must be labeled. |
| CGST/SGST/IGST classification, place of supply, legally required invoice fields, and tax invoice layout/number acceptance | Business/accounting owner; before live tax invoices | Generic quote tax snapshot only; block real tax invoice if context is incomplete. |
| Stock deduction trigger and shortage-after-payment remedy | Rehbar + wholesaler + Fareed; before automatic order confirmation | Quote and link checks never reserve/deduct; paid shortage enters manual review, no automatic invoice. |
| Refunds, chargebacks, partial payments, customer tiers, promotions, ERP/sheet sync | Later product scope | No state or calculation is silently inferred. |
| Multiple Razorpay merchant accounts and webhook-secret routing | Fareed + business onboarding; before a second live business | One configured merchant account for MVP; provider link maps to mandatory business ID. |
| Exact internal transport for Rehbar approval/issuance evidence | Rehbar + Fareed; before Phase 3 quote issuance | Evidence shape and exact-version checks are frozen; no quote becomes `GENERATED` from an untrusted boolean. |
| AWS persistence and artifact hosting target | Team; before deployment design | Local PostgreSQL and local artifact adapter contract; no DynamoDB/RDS/S3 migration implied now. |

The contract is ready for Phase 1 schema design because the identity keys, business scoping, immutable quote version/snapshot, money type, states, uniqueness boundaries, and invoice/payment linkage are frozen. The deferred numeric and legal inputs are data/configuration or later feature gates, not permission to create fabricated values.

## 17. Phase 1 Implementation Consequences

**Do not implement Phase 1 in this task.** When it begins, model the frozen keys and relationships with `business_id NOT NULL`, a minimal buyer record, version-specific quote IDs, separate local/provider payment IDs, event/idempotency uniqueness, and business-scoped invoice sequence and artifact status. Do not add a Fareed-owned run lifecycle table, a quote `PAID` state, a stock reservation balance, or a giant CRM. Register only approved SQLAlchemy models in `server/app/db/base.py`; review Alembic DDL and test against an isolated PostgreSQL database. The empty `0001_baseline` revision remains untouched here.

Before exposing any commercial route, implement a trusted caller/business-scope check and normalized error envelope; before real Razorpay payments, configure secrets and signed webhooks; before tax invoices, confirm seller/buyer and GST presentation. Rehbar's run/approval integration, Yunus's screens, and Amir's fixture/QA work can proceed against this contract in parallel.
