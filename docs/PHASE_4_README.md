# StockAware Phase 4 — Payment Links and Verified Payment

## Scope and status

This checkpoint adds local payment intents, Razorpay Standard Payment Link
creation, signed webhook processing, payment reads, and durable payment outbox
records. Automated tests use a fake provider and disposable PostgreSQL; no
live Razorpay call or money movement was made. The frozen commercial contract
remains [contracts.md](contracts.md). No new database migration is needed.

The implementation is **not a live-payment launch approval**. Reference lookup
now recovers a verified existing link after an ambiguous create result; unresolved
negative lookups, provider-confirmed cancellation/expiry, merchant validation,
outbox delivery, and Rehbar integration remain live-release gates.

## Internal API and configuration

`POST /payments/create-link` requires `X-Internal-Service-Token` and a unique
`Idempotency-Key`. The body carries authorized `business_id`, stable `run_id`,
exact `quote_id` and `quote_version`, and optionally `amount_paise` as a
comparison assertion. The amount sent to Razorpay always comes from the frozen
quote. Response includes local `payment_id`, `PENDING` status, exact amount and
currency, provider link ID, safe payment URL, and expiry. `GET /payments/{id}`
requires the same service identity and returns only a business-scoped safe
projection. `POST /payments/webhook` is public to Razorpay but is authenticated
by the configured webhook HMAC signature, not by the internal token.

Configuration is fail-closed: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
`RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_ACCOUNT_ID`, and optionally
`RAZORPAY_PREVIOUS_WEBHOOK_SECRET` for a controlled rotation overlap. Set these
only in ignored local environment or a managed deployment secret store. The
current internal token maps to a single configured business ID; it is not a
general multi-tenant authentication system. Docker Compose passes the same
server-side variables. Never put these values in `NEXT_PUBLIC_*` variables.

## Link preconditions and transaction boundaries

Before the external call, a PostgreSQL transaction claims the business/action
idempotency key, locks the exact current quote, and checks run/version,
unexpired `ACCEPTED` status, acceptance evidence, required approval, frozen
amount/currency, and current inventory for all frozen quote lines. Stock is
read-only; it is neither reserved nor deducted. The transaction persists a
`CREATED` intent and unique reference ID derived from its UUID. The Razorpay
call occurs **outside** the database transaction. A second transaction verifies
the returned link reference/amount/currency and stores its ID/URL and `PENDING`
state with the completed idempotency result.

Same-key/same-request replays return the saved response; changed payloads
return `IDEMPOTENCY_CONFLICT`. A quote version with any prior local payment
intent cannot get another link through this endpoint, including after a
locally failed/expired attempt, until its provider reference is reconciled.
An ambiguous provider timeout leaves `CREATED` plus a `PROCESSING` key and
returns `PROVIDER_OUTCOME_UNKNOWN`. A same-key retry looks up Razorpay's unique
reference; an exact valid link is attached. Empty/uncertain lookup does **not**
blindly create another link. See [post-audit remediation](POST_AUDIT_REMEDIATION.md)
for validation and remaining operational holds.

The local state vocabulary is `CREATED`, `PENDING`, `PAID`, `FAILED`,
`EXPIRED`, `CANCELLED`; this checkpoint actively writes `CREATED`, `PENDING`,
and signed-event-verified `PAID`. The other provider-confirmed state
transitions need their reconciliation/cancellation adapter before live use.
Late signed payment after local expiry/cancellation is still recorded as
`PAID` with `reconciliation_hold=true`, never discarded.

## Webhook validation and outbox

The webhook reads exact raw request bytes, checks HMAC-SHA256 with
`hmac.compare_digest()` against current/previous configured webhook secret,
and only then parses JSON. The signed account must match the configured
merchant account, and the provider link must resolve to a local payment.
`payment_link.paid` requires a captured payment, paid link, full `amount_paid`,
same amount on both entities, INR, and matching reference if supplied.
`payment.authorized`, partial amounts, wrong currency, or a buyer/client claim
cannot mark `PAID`.

`(provider, account, event_id)` is unique. Exact byte-identical replay returns
`duplicate=true` with no second transition or outbox event; same ID with
different bytes returns `DUPLICATE_EVENT`. A signed mismatch is persisted with
a safe hash/metadata and a `payment.reconciliation_required` outbox record;
it is acknowledged without marking the payment paid. The verified-event row,
legal `PAID` transition, and `payment.verified` outbox record commit atomically.
If stock is short by the time a valid payment arrives, or provider time is at
or beyond link expiry, payment truth remains `PAID` but automatic progression
is held. A second distinct captured provider payment likewise sets a hold.
No raw webhook body or secret is stored in the event/outbox tables.

The outbox is a **database-side production boundary only**. No Redis, Kafka,
SQS, or Rehbar delivery transport has been invented. A future authenticated
consumer must process `payment.verified`/`payment.reconciliation_required`
idempotently, publish only after commit, and record `published_at`.

## Rehbar, frontend and QA

Rehbar must send exact quote/run/version only after its trusted approval and
buyer-acceptance evidence has been applied to the Fareed quote. A Rehbar
run status does not mark a payment paid. On committed `payment.verified`, it
can advance its workflow unless `reconciliation_hold` is set. Yunus displays
the returned URL and exact paise amount but never sets payment status from a
browser redirect. Buyer-facing payment access still needs constrained auth;
the current GET endpoint is internal-only.

Phase 4 tests cover preconditions, stock recheck, idempotency, uncertain
provider outcome, raw formatting trap, signature rotation, mismatch
quarantine, event replay/conflict, late payment hold, business scoping and
PostgreSQL persistence using a fake provider. Run `make test-pg`, Ruff, and
Compose validation. There has been no live-credential verification.

Razorpay API behavior used here is based on its [Standard Payment Link API](https://razorpay.com/docs/api/payments/payment-links/), [link states](https://razorpay.com/docs/payments/payment-links/states/), and [webhook validation guide](https://razorpay.com/docs/webhooks/validate-test/).
