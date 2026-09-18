# Adversarial Code Review Checklist

Use this checklist during the morning audit of Codex's production backend implementation.

## Phase 2: Catalog & Inventory
- [ ] Check for `.first()` ambiguity leaks. Did they use `fetch_one()` with proper limits?
- [ ] Check for global queries missing the `business_id` filter (cross-business leak).
- [ ] Check for "fuzzy" fallback searches (contract forbids this).
- [ ] Ensure `inventory/check` does NOT write to the DB (read-only invariant).

## Phase 3: Pricing & Quotes
- [ ] **CRITICAL:** Search for `float` types or `float()` casts. All pricing MUST use `Decimal`.
- [ ] Search for built-in `round()`. MUST use `.quantize(Decimal('1'), rounding=ROUND_HALF_UP)`.
- [ ] Check quote mutation: existing versions MUST NOT be mutated; must insert new version.
- [ ] Check for missing lineage locks on version generation.
- [ ] Ensure background expiry doesn't bypass inline wall-clock expiry checks.

## Phase 4: Payments & Webhooks
- [ ] **CRITICAL:** Check if FastAPI parses the webhook body into a Pydantic model *before* the HMAC check. It MUST read raw bytes.
- [ ] Check if `json.dumps()` is used to re-serialize the body for HMAC (this corrupts spacing/unicode).
- [ ] Check for `==` instead of `hmac.compare_digest()` (timing attack risk).
- [ ] Check if `authorized` webhooks incorrectly mark payment as `PAID`.
- [ ] Ensure event, payment, and outbox writes are inside a single atomic transaction.

## Phase 5: Invoices
- [ ] Ensure the invoice snapshot copies strings (Name/SKU) rather than doing a live DB JOIN.
- [ ] Check sequence locks: Are sequence numbers generated inside a safe `FOR UPDATE` lock?
- [ ] Ensure PDF generation errors do not cause the sequence number to increment permanently.
- [ ] Check that `PENDING_ARTIFACT` status exposes NO `download_url`.
