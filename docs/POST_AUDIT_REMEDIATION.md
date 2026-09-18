# StockAware post-audit release hardening

This checkpoint follows the independent audit of `ae7a75e`. The working branch
also contains the later `origin/main` merge, so the local in-memory demo router
was reviewed separately. This is **not** live-payment or tax-invoice approval.

## Internal service authentication

Commercial HTTP routes use a server-side `X-Internal-Service-Token`. Configure
`INTERNAL_SERVICE_TOKEN` as a high-entropy secret and `INTERNAL_BUSINESS_ID`
as the UUID of the **one** business this credential may assert. Neither is
taken from the request body. Missing configuration returns the canonical 503
`AUTHORIZATION_NOT_CONFIGURED`; missing/wrong credential returns 401
`UNAUTHORIZED`. A malformed configured business UUID fails closed. Correct
credentials bind all DB lookups to the configured business; mismatched
body-supplied business IDs return scoped 404 without disclosing another tenant.
The comparison is constant-time. Rotate the token by coordinating a server-side
secret update and caller rollout; a second-token overlap is not implemented.

For local Compose, use the ignored `.env`. For ECS, set
`internal_business_id` and `internal_service_token_ssm_arn` Terraform
inputs. The latter points to an **externally managed SSM SecureString**; the
token value is not a Terraform input or stored in Terraform state by this
checkpoint. The ECS task execution role is granted read access to that ARN.
Empty inputs deliberately keep commercial routes unavailable. The Rehbar
caller must hold the credential server-side and supply it on internal HTTP
requests, never in WhatsApp messages or browser JavaScript. If Rehbar and
Fareed call services in the same FastAPI process, direct trusted service calls
do not need a loopback HTTP credential, but the externally callable commercial
routes still enforce this dependency. Rehbar's approval/acceptance evidence
transport and its own route authentication remain separately deferred.

| Endpoint | Allowed caller today | Buyer/browser access |
| --- | --- | --- |
| `GET /products` | Internal Rehbar/admin service | None |
| `POST /catalog/match` | Internal Rehbar/admin service | None |
| `POST /inventory/check` | Internal Rehbar/admin service | None |
| `POST /pricing/quote` | Internal Rehbar/admin service | None |
| `POST /payments/create-link` | Internal Rehbar service after evidence | None |
| `GET /payments/{payment_id}` | Internal Rehbar/admin service | None |
| `POST /invoice/generate` | Internal Rehbar/admin service after verified payment | None |
| `GET /invoices/{invoice_id}` | Internal Rehbar/admin service | None |
| `GET /invoices/{invoice_id}/artifact` | Internal Rehbar/admin service | None |
| `POST /payments/webhook` | Razorpay, authenticated by raw-body HMAC | None |

A buyer read surface requires separate buyer authorization/capability. Yunus's
frontend must not contain the internal token, Razorpay key/webhook secret, cost
data, margin policy, or controls that assert `PAID`, owner approval, or buyer
acceptance. CORS is not authentication. The local `/demo/*` in-memory workflow
is excluded from production app registration; it is never payment truth.

## Uncertain Razorpay creation result

The payment intent and unique `provider_reference_id` (the local payment UUID)
commit before the provider POST. The official [Razorpay Payment Links API](https://razorpay.com/docs/api/payments/payment-links/) documents unique
`reference_id`; Razorpay's [reference-filtered fetch example](https://d6xcmfyh68wv8.cloudfront.net/docs/api/payments/payment-links/)
shows `GET /v1/payment_links/?reference_id=...`. This lookup uses the same
merchant Basic Auth credentials as creation. No live/test-mode link is created
by automated tests.

On retry with the **same** business/action/idempotency key and fingerprint:

1. Return a previously completed response unchanged.
2. Otherwise read the persisted intent/reference in a short transaction.
3. Outside any DB transaction, fetch by that exact reference.
4. A uniquely returned link is bound only after reference, amount, INR
   currency, status, HTTPS URL, provider ID, local merchant account key, and
   prior binding are checked under the locked payment row.
5. A returned `paid` link remains locally `PENDING` with a reconciliation
   hold until a signed paid webhook establishes payment truth. No lookup alone
   generates an invoice.
6. Empty, malformed, ambiguous, timed-out, or mismatched lookup **never**
   triggers another provider create. Empty is not considered authoritative
   absence because the provider docs do not promise a strongly consistent
   negative lookup after a timed-out POST.

A duplicate key with changed payload returns `IDEMPOTENCY_CONFLICT`. A second
key cannot bypass the existing one-intent-per-quote constraint. Webhooks that
arrive before the link ID is bound remain unrecognized (non-2xx); after link
recovery a signed retry can be processed. Operational replay/reconciliation is
needed if Razorpay stops retrying before recovery. Provider account membership
is enforced by the configured merchant credentials and the local account key;
the lookup response does not expose an independently verifiable account ID.
Merchant test-mode verification and provider-confirmed cancellation/expiry are
still required before live launch.

## Remaining release gaps

- **High / external integration:** trusted Rehbar approval/acceptance transport,
  owner identity verification, and audit of Rehbar-owned endpoints.
- **Medium / operations:** durable outbox *delivery* to Rehbar, stuck-intent
  monitoring/manual reconciliation, and provider-confirmed cancel/expire/fail.
- **Low / scalability:** PDF rendering currently occurs synchronously. This is
  safe for current demo/load assumptions but may increase HTTP latency.
  Background artifact generation is future work; the existing
  `PENDING_ARTIFACT → GENERATED` retry lifecycle is unchanged.
- **Deferred business:** real SKU/stock/pricing policy, GST and legal invoice
  fields/format, and stock deduction trigger need owner/accounting decisions.
- **Deferred external:** buyer auth, multi-business service identities, merchant
  credentials/test-mode validation, production artifact storage/backup and
  observability. No browser may reuse the internal service token.

The audited catalog, inventory, pricing, quote snapshot, raw-webhook HMAC,
outbox atomicity, invoice sequence and PDF retry invariants were not rewritten.
