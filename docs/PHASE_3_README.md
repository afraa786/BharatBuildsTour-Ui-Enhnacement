# StockAware Phase 3 — Pricing and Quote Engine

## Scope

Phase 3 implements exact INR pricing and the contracted `POST /pricing/quote`
API. It persists version-specific quote and line snapshots using the frozen
Phase 1 tables. There is **no new migration**. No Razorpay, payment link,
invoice, stock reservation, or Rehbar workflow mutation is implemented here.

The authoritative rules remain [contracts.md](contracts.md). This API is
internal-only behind the Phase 2 `X-Internal-Service-Token` business context.
The body `business_id` is validated against the token's authorized business;
it cannot select another business.

## API

```http
POST /pricing/quote
X-Internal-Service-Token: <internal token>
Idempotency-Key: <unique key for this intended version>
Content-Type: application/json

{"business_id":"ff720599-56e8-53f4-9279-27ae059da37f","run_id":"RFQ-1042","buyer_id":"<business-scoped buyer UUID>","lines":[{"product_id":"dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7","quantity":"2.000","unit":"piece","discount_bps":0}]}
```

For a demo business configured with `approval_required_for_all=false`, the
unmodified `LED-9W` seed yields the following commercial amounts:

```json
{
  "status": "GENERATED",
  "currency": "INR",
  "subtotal_paise": 24000,
  "tax_paise": 4320,
  "total_paise": 28320,
  "approval_required": false,
  "approval_satisfied": false,
  "approval_reasons": [],
  "lines": [{"sku":"LED-9W","quantity":"2.000","unit":"piece","unit_price_paise":12000,"discount_bps":0,"discount_paise":0,"taxable_paise":24000,"gst_rate_bps":1800,"tax_paise":4320,"line_total_paise":28320}]
}
```

Actual response also contains `business_id`, `run_id`, immutable `quote_id`,
positive `quote_version`, UTC `expires_at`, and safe line `product_id`/`name`.
The demo seed's default owner policy is `approval_required_for_all=true`, so
without the explicit test configuration above it returns a `DRAFT` with
`approval_required=true` and `OWNER_APPROVAL_POLICY` reason. The example does
not change the seed or declare live owner policy.

One active, effective business pricing rule and a configured quote validity
period are required. An absent rule or validity configuration fails rather
than selecting a default. The buyer and active products must belong to the
authorized business. Quantities are positive decimal strings at no more than
three fractional places and use each product's sellable unit. Indivisible
products reject fractional quantities.

## Arithmetic and policy

Each line uses integer paise and `Decimal` with `ROUND_HALF_UP`:

1. `gross = HALF_UP(unit_price_paise × quantity)`.
2. `discount = HALF_UP(gross × requested_discount_bps / 10000)`.
3. `taxable = gross − discount`.
4. `tax = HALF_UP(taxable × configured_product_gst_bps / 10000)`.
5. `line_total = taxable + tax`.

The quote subtotal and tax are sums of the already rounded line values;
there is no quote-level rerounding. Zero/negative taxable revenue is invalid,
not an approvable quote. Amounts exceeding signed PostgreSQL `BIGINT` paise
range fail validation. No float or built-in `round()` determines money.

A requested discount above `max_discount_bps` remains requested and priced;
it is **not clipped**. The line receives `DISCOUNT_EXCEEDS_CAP`. Gross margin
compares `(taxable − rounded_cost) × 10000` with
`min_margin_bps × taxable`, without float percentages; a shortfall receives
`MARGIN_BELOW_FLOOR`. Business owner-all-quote approval and missing approval
preference also fail closed with explicit reasons. Any reason makes the new
quote a `DRAFT` requiring Rehbar owner evidence before issuance.

## Snapshots, versions, and idempotency

The quote freezes buyer display/contact/billing data, pricing rule ID/version,
policy thresholds and reasons, seller/buyer tax context, currency, expiry,
line SKU/name/unit/pack, cost, base price, discount, GST rate, rounded
intermediates, and totals. Buyer-safe API responses omit cost and threshold
values. Later catalog, buyer, or rule edits do not rewrite historical values.
Tax classification remains unset because the business/accounting decision is
deferred; a real tax invoice is not authorized by this generic tax snapshot.

`run_id` is the lineage. Each successful new intended revision has a new UUID
`quote_id` and incremented `quote_version`. A PostgreSQL lineage-row lock and
the partial current-version unique index serialize concurrent revisions.
Prior unpaid/current versions become `CANCELLED` and non-current atomically.
Unsettled `CREATED`/`PENDING`/`PAID`/`FAILED` payment records block a revision
until provider reconciliation; this phase never guesses that a live link was
cancelled. Stale versions are not valid approval/acceptance targets.

`Idempotency-Key` is mandatory on `POST /pricing/quote`, scoped to business and
`pricing.quote`. The canonical request fingerprint includes `run_id` and
normalized decimal quantities. A same-key/same-request replay returns the
original creation response without a new version; same key with changed input
returns `IDEMPOTENCY_CONFLICT` (409). Claim, lineage update, quote/items, and
completed replay record are one PostgreSQL transaction. Parallel tests verify
one current version and one response per same-key race.

## Rehbar evidence boundary

Rehbar remains the source of owner approval and buyer acceptance. Phase 3
provides **internal service functions**, not guessed public HTTP paths:

- `apply_approval(session, evidence, authorized_actor_ids=...)` requires
  business/run/quote/version, approval/action IDs, `approve_quote` action,
  authorized owner actor, approved decision, timestamp, and unrevoked/unexpired
  evidence. It moves the exact current `DRAFT` to `GENERATED`.
- `apply_acceptance(session, evidence)` requires the same exact quote binding,
  Rehbar's acceptance ID, verified WhatsApp buyer contact, source message ID,
  channel, and timestamp after issuance but before expiry. It moves
  `GENERATED` to `ACCEPTED`.

The calling adapter **must authenticate Rehbar and verify evidence provenance
before invoking these functions**. The exact transport remains a frozen-contract
deferred decision; no browser-supplied `approved: true` or `accepted: true` is
trusted. Authenticated quote-page acceptance is not enabled yet. Duplicate
identical evidence is harmless; same-ID changed evidence conflicts. Evidence
does not mutate immutable financial fields. Expiry is checked inline.

## For Rehbar

Send only resolved Phase 2 product IDs, positive decimal-string quantities,
exact sellable units, stable `run_id`, scoped buyer ID, and a new idempotency key
for each intended revision. A `DRAFT` needs exact-version owner approval before
it is an issuable offer. A `GENERATED` quote may be sent to the buyer; record
send state in Rehbar's run, not in the quote row. Record buyer acceptance
separately, then hand verified evidence to Fareed before Phase 4 link creation.
Do not use a stale quote UUID/version or assume a quote is payable from a
Rehbar status alone.

## For Frontend

Show the returned integer-paise totals, line taxes, currency, expiry, status,
approval flag/reasons where the authenticated owner is allowed to see them,
and exact `quote_id`/`quote_version`. Never calculate authoritative totals in
JavaScript floats. Do not display private margin/cost from snapshots; the
public API does not include them. A buyer-facing artifact/page and its
authentication are later integration work.

## Verification and fixture discrepancies

`server/tests/test_phase3_money.py`, `test_phase3_money_limits.py`,
`test_phase3_postgres.py`, and `test_phase3_concurrency.py` cover arithmetic,
rounding, policy, snapshots, evidence, idempotency, revisions, and real
PostgreSQL races. Run `make test-pg` and the standard quality gates.

Two independent harness pricing vectors currently disagree with
`docs/contracts.md`: its above-cap example describes discount clipping, and
its 100% discount example treats zero taxable revenue as approvable. Production
follows the frozen contract: no silent clipping, and zero taxable is invalid.
The QA harness is independently owned and is not edited here. Its 6413-paise
tax and per-line rounding boundaries are reproduced by production tests.

## Deferred

Rehbar evidence transport and business-specific owner actor mapping; buyer
identity creation/onboarding API; live quote send artifact; legal GST
classification; production numeric pricing and approval policy confirmation;
Razorpay/payment and invoice functions. None is silently inferred here.
