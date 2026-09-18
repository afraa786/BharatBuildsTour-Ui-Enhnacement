# API Acceptance Mapping

This maps the fixtures in the `scratch/integration_harness` to live expected HTTP endpoints when Codex implements them.

## Phase 3: Pricing & Quotes
- **Capability:** `quote.generate`
- **Method:** `POST`
- **Path:** `IMPLEMENTATION-DEFINED`
- **Request Fixture:** `fixtures/pricing/golden_vectors.json` (inputs)
- **Expected DB Post-State:** Inserted `Quote` and `QuoteLineItem` if valid. Version increments.
- **Invariant:** Must match `pricing_oracle.py` outputs.

## Phase 4: Payments
- **Capability:** `payment.create_link`
- **Method:** `POST`
- **Path:** `IMPLEMENTATION-DEFINED`
- **Preconditions:** Quote MUST be `ACCEPTED`. Stock MUST remain sufficient.
- **Invariant:** Generates a Provider link ID and local Payment ID.

- **Capability:** `webhook.receive`
- **Method:** `POST`
- **Path:** `IMPLEMENTATION-DEFINED`
- **Request Fixture:** `fixtures/webhooks/*.raw.json`
- **Invariant:** MUST verify raw byte HMAC signature. Idempotent processing.

## Phase 5: Invoices
- **Capability:** `invoice.generate`
- **Method:** `POST`
- **Path:** `IMPLEMENTATION-DEFINED`
- **Invariant:** `PENDING_ARTIFACT` locked status until PDF is generated. Sequence numbers must never gap.
